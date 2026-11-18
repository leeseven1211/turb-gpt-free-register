#!/usr/bin/env python3
"""以同一固定内存数据服务旧/新任务中心资源，不加载业务或数据库。

先将基线 Git 的 webui/static 与 webui/templates 导出到独立目录，再用
--asset-root 分别指定基线目录与当前目录。仅监听127.0.0.1。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jinja2 import FileSystemLoader
from tools.diagnostics.preview_task_center import create_preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path, default=ROOT)
    parser.add_argument("--port", type=int, default=8019)
    parser.add_argument("--tasks", type=int, default=2000)
    args = parser.parse_args()
    assets = args.asset_root.resolve()
    if not (assets / "webui/templates/index.html").is_file():
        parser.error("资源目录必须包含 webui/templates/index.html")
    app = create_preview(task_count=args.tasks, now=datetime(2026, 11, 13, 0, 0, tzinfo=timezone.utc), event_page_size=500)
    app.static_folder = str(assets / "webui/static")
    app.jinja_loader = FileSystemLoader(str(assets / "webui/templates"))
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
