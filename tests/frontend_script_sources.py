"""读取模板实际加载的账号页面脚本，供前端契约测试使用。"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_FILES = {
    "accounts.js", "account-tasks.js", "account-email-change.js", "account-inspection.js",
}


def read_account_script(name: str) -> str:
    template = (ROOT / "webui/templates/index.html").read_text(encoding="utf-8")
    loaded = re.findall(r"filename='js/modern/([^']+)'", template)
    if name not in ACCOUNT_FILES or loaded.count(name) != 1:
        raise AssertionError(f"账号页面未唯一加载 {name}")
    return (ROOT / "webui/static/js/modern" / name).read_text(encoding="utf-8")
