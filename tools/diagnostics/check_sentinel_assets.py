#!/usr/bin/env python3
"""Inspect Sentinel candidate assets; network access requires --refresh."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from core.auth.protocol.sentinel_assets import SentinelAssetManager  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", required=True, type=Path, help="Dedicated candidate cache directory")
    parser.add_argument("--refresh", action="store_true", help="Explicitly fetch official public loader and SDK")
    parser.add_argument("--json", action="store_true", help="Print a safe machine-readable summary")
    parser.add_argument("--ttl", type=float, default=86400, help="Cache freshness in seconds (does not trigger fetching)")
    parser.add_argument("--timeout", type=float, default=15, help="Shared download and cache lock timeout in seconds")
    args = parser.parse_args(argv)
    try:
        manager = SentinelAssetManager(args.cache_dir, ttl_seconds=args.ttl, timeout_seconds=args.timeout)
    except ValueError as error:
        parser.error(str(error))
    result = manager.check(refresh=args.refresh)
    if args.json:
        print(json.dumps(result.to_dict(), sort_keys=True))
    else:
        print(f"Candidate check: {result.status}" + (f" ({result.reason})" if result.reason else ""))
        if result.artifact:
            artifact = result.artifact
            print(f"Version: {artifact.version}\nSHA256: {artifact.sha256}\nCandidate: {artifact.path}")
            report = artifact.compatibility
            print(f"Generic: {report.generic_status}; Proto2: {report.proto2_status}")
            print("Proto2 hook hits: " + ", ".join(f"{name}={hits}" for name, hits in report.proto2_hooks))
            print("Static checks only; runtime verification: false. Candidate activation requires a separate review.")
        else:
            print("Use --refresh to explicitly fetch candidate resources.")
    return 0 if result.status in {"cached", "refreshed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
