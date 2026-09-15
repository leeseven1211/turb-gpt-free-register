#!/usr/bin/env python3
"""显式把外部 Outlook 素材文件导入 PostgreSQL 邮箱池。"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from core import postgres_store  # noqa: E402
from core.outlook_client import import_outlook_from_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="将外部 Outlook 素材文件导入 PostgreSQL 邮箱池")
    parser.add_argument("--file", required=True, type=Path, help="外部输入文件路径；不会被改写或复制")
    parser.add_argument("--verbose", action="store_true", help="显示导入诊断日志")
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    postgres_store.require_ready()
    inserted, skipped = import_outlook_from_file(args.file)
    print(f"inserted={inserted} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
