#!/usr/bin/env python3
"""Check a running WebUI without mutating the process or database."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ProbeResult:
    """Safe summary of one HTTP probe."""

    path: str
    status_code: int | None
    ok: bool
    error: str = ""


def _request_json(base_url: str, path: str, timeout: float) -> ProbeResult:
    url = f"{base_url.rstrip('/')}{path}"
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    status_code: int | None = None
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = int(response.status)
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return ProbeResult(path, int(exc.code), False, f"http_{int(exc.code)}")
    except (URLError, TimeoutError, OSError) as exc:
        return ProbeResult(path, None, False, type(exc).__name__)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return ProbeResult(path, status_code, False, "invalid_json")

    if not isinstance(body, dict):
        return ProbeResult(path, status_code, False, "response_not_object")
    if path == "/healthz":
        valid = status_code == 200 and body.get("ok") is True and body.get("status") == "alive"
    else:
        checks = body.get("checks") if isinstance(body.get("checks"), dict) else {}
        valid = (
            status_code == 200
            and body.get("ok") is True
            and body.get("status") == "ready"
            and isinstance(checks.get("database"), dict)
            and checks["database"].get("ok") is True
            and isinstance(checks.get("runtime"), dict)
            and checks["runtime"].get("ok") is True
        )
    return ProbeResult(path, status_code, valid, "" if valid else "contract_mismatch")


def check_startup(base_url: str, *, timeout: float = 3.0) -> list[ProbeResult]:
    """Check HTTP liveness followed by database and worker readiness."""
    return [
        _request_json(base_url, "/healthz", timeout),
        _request_json(base_url, "/readyz", timeout),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 WebUI HTTP、PostgreSQL 与 worker readiness")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="WebUI 根 URL")
    parser.add_argument("--timeout", type=float, default=3.0, help="单次 HTTP 超时秒数")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        print("startup check failed: timeout 必须大于 0", file=sys.stderr)
        return 2
    results = check_startup(str(args.base_url), timeout=float(args.timeout))
    for result in results:
        suffix = f" error={result.error}" if result.error else ""
        print(f"{result.path}: status={result.status_code or 'unreachable'} ok={result.ok}{suffix}")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
