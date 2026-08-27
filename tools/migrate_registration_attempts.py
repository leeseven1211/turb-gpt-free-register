#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Additive migration/backfill for registration Attempt/Run facts.

The default mode only reports counts.  ``--apply`` creates the new tables and
backfills existing registration_jobs.  ``--verify`` never deletes or rewrites
legacy tables and returns a non-zero status when an invariant is broken.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.env_loader import ensure_loaded  # noqa: E402
from core import postgres_store  # noqa: E402
from core.storage import registration  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="幂等迁移 registration Attempt/Run/Checkpoint 事实")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="创建/升级表并回填历史 registration_jobs")
    mode.add_argument("--verify", action="store_true", help="只验证迁移不变量")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    args = parser.parse_args()

    ensure_loaded()
    postgres_store.require_ready()
    if args.apply:
        result = {"mode": "apply", "backfill": registration.backfill(apply=True), "verification": registration.verify()}
    elif args.verify:
        result = {"mode": "verify", "verification": registration.verify()}
    else:
        result = {"mode": "dry_run", "backfill": registration.backfill(apply=False)}
    print(json.dumps(result, ensure_ascii=False, indent=None if args.json else 2, default=str))
    verification = result.get("verification")
    return 0 if not verification or verification.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
