"""读取模板实际加载的账号页面脚本，供前端契约测试使用。"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_FILES = {
    "accounts.js": "js/pages/accounts/page.js",
    "account-tasks.js": "js/pages/operations/page.js",
    "account-email-change.js": "js/pages/accounts/email-change.js",
    "account-inspection.js": "js/pages/accounts/inspection.js",
}


def read_account_script(name: str) -> str:
    template = (ROOT / "webui/templates/index.html").read_text(encoding="utf-8")
    loaded = re.findall(r"filename='([^']+)'", template)
    if name not in ACCOUNT_FILES or loaded.count(ACCOUNT_FILES[name]) != 1:
        raise AssertionError(f"账号页面未唯一加载 {name}")
    return (ROOT / "webui/static" / ACCOUNT_FILES[name]).read_text(encoding="utf-8")
