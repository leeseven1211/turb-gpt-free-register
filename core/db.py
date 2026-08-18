# -*- coding: utf-8 -*-
"""
业务数据持久化层。

配置 DATABASE_URL 后以 PostgreSQL 为主存储；现有 JSON/TXT 继续作为兼容导出。

根目录文件分工：
    - 用于注册的邮箱.txt      仅保留可继续注册的邮箱素材
    - 注册成功的邮箱.txt      仅保存注册成功的邮箱素材，不追加 token
    - 注册成功的token.txt     每行只保存一个 access token
    - 用于注册的邮箱.json     Outlook 账号池完整状态
    - 注册成功的邮箱.json     注册成功账号完整状态
"""
import hashlib
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any

from core import postgres_store, record_store

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _PROJECT_ROOT
_LEGACY_DATA_DIR = _PROJECT_ROOT / "data"
_LOG_DIR = _PROJECT_ROOT / "注册日志"
_PLAN_CHECK_STALE_SECONDS = 120
_PLAN_CHECK_QUEUE_STALE_SECONDS = 1800

_OUTLOOK_JSON = _PROJECT_ROOT / "用于注册的邮箱.json"
_OUTLOOK_TXT = _PROJECT_ROOT / "用于注册的邮箱.txt"
_GENERIC_API_EMAIL_JSON = _PROJECT_ROOT / "用于注册的API邮箱.json"
_GENERIC_API_EMAIL_TXT = _PROJECT_ROOT / "用于注册的API邮箱.txt"
_ACCOUNTS_JSON = _PROJECT_ROOT / "注册成功的邮箱.json"
_ACCOUNTS_TXT = _PROJECT_ROOT / "注册成功的邮箱.txt"
_TOKENS_TXT = _PROJECT_ROOT / "注册成功的token.txt"
_JOBS_JSON = _PROJECT_ROOT / "注册任务.json"
_VIEWER_HTML = _PROJECT_ROOT / "accounts_viewer.html"
_CODEX_DIR = _PROJECT_ROOT / "codex_accounts"
# 导出状态单独存：{ "codex-邮箱-plan.json": {"exported_at": "...", "exported_count": N} }
# 不污染 CPA 兼容的原文件
_CODEX_EXPORT_STATE = _PROJECT_ROOT / "codex_导出状态.json"
_CODEX_CREDENTIALS_COLLECTION = "codex_credentials"

_LEGACY_OUTLOOK_JSON = _LEGACY_DATA_DIR / "outlook_accounts.json"
_LEGACY_ACCOUNTS_JSON = _LEGACY_DATA_DIR / "registered_accounts.json"
_LEGACY_JOBS_JSON = _LEGACY_DATA_DIR / "registration_jobs.json"
_LOCK = threading.RLock()

JOB_PROGRESS_STAGES = (
    ("email", "准备邮箱"),
    ("browser", "启动浏览器"),
    ("page", "打开注册页"),
    ("submit_email", "提交邮箱"),
    ("auth_redirect", "认证跳转"),
    ("email_otp", "邮箱验证码"),
    ("profile", "填写资料"),
    ("token", "获取 Token"),
    ("codex", "Codex 授权"),
    ("plan_check", "查套餐"),
    ("complete", "完成"),
)
_JOB_PROGRESS_KEYS = tuple(key for key, _label in JOB_PROGRESS_STAGES)
_JOB_PROGRESS_STATES = {"pending", "running", "success", "failed", "skipped", "stopped"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_storage() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    """从 PostgreSQL 读取集合。PG 不可用时直接抛错，不回退兼容文件。

    回退看起来更"健壮"，实际是让两份副本悄悄分叉——读到旧文件、写回 PG，
    中间的变更就没了。宁可响亮失败。
    """
    _ensure_storage()
    collection = _collection_name(path)
    found, payload = postgres_store.load_collection(collection)
    if found:
        return payload
    # PG 里还没有这个集合：用兼容文件做一次性种子。迁移完成后此路径会移除。
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    postgres_store.save_collection(collection, payload)
    return payload


def _write_json(path: Path, data: Any) -> None:
    _ensure_storage()
    postgres_store.save_collection(_collection_name(path), data)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def _collection_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(_PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


# ============================================================
# 表接缝：_load_X / _save_X 底下由 record_store 的行级表支撑
#
# 保留"整表 list[dict] 进出"的形状，是为了让 60 多个调用方不必改写；但落库时
# 只写真正变化的行，而不是把整个集合重新序列化一遍。真正需要行级语义的地方
# （抢占、热点单字段更新、跨表事务）另有直连 record_store 的实现。
# ============================================================

def _load_table(spec) -> list[dict]:
    return record_store.list_rows(spec, order_by="id")


def _row_signature(row: dict) -> str:
    """用于判断一行是否变化。派生字段不参与，避免它自己触发一次写。"""
    return json.dumps(
        {k: v for k, v in row.items() if k != "copy_line"},
        ensure_ascii=False, sort_keys=True, default=str,
    )


def _sync_table(spec, rows: list[dict], *, conn=None) -> None:
    """把整表快照落到行级表，只写差异行。

    这是旧"读全量→改→写全量"调用方与行级存储之间的桥。相比原来每次重写
    2 MB+ JSONB，这里通常只发一条 UPDATE。

    传入 conn 可以把多张表的写入并入同一个事务——insert_account 之类要同时改
    账号和邮箱池，分两次提交会留下"账号建好了但邮箱没标记 used"的中间态。
    """
    current = {int(r["id"]): r for r in record_store.list_rows(spec, order_by="id")
               if r.get("id") is not None}
    seen: set[int] = set()

    def _apply(active) -> None:
        for row in rows:
            rid = row.get("id")
            if rid is None:
                new_id = record_store.insert_row(spec, row, conn=active)
                row["id"] = new_id
                seen.add(int(new_id))
                continue
            rid = int(rid)
            seen.add(rid)
            existing = current.get(rid)
            if existing is None:
                record_store.insert_row(spec, row, conn=active)
            elif _row_signature(existing) != _row_signature(row):
                record_store.patch_row(spec, rid, row, conn=active)
        removed = [rid for rid in current if rid not in seen]
        if removed:
            record_store.delete_rows(spec, removed, conn=active)

    if conn is not None:
        _apply(conn)
        return
    with record_store.transaction() as own:
        _apply(own)


def _next_id(items: list[dict]) -> int:
    ids = [int(item.get("id") or 0) for item in items]
    return (max(ids) if ids else 0) + 1


def _outlook_line(row: dict) -> str:
    return "----".join([
        row.get("email") or "",
        row.get("password") or "",
        row.get("client_id") or "",
        row.get("refresh_token") or "",
    ])


def _generic_api_email_line(row: dict) -> str:
    return "----".join([
        row.get("email") or "",
        row.get("code_url") or "",
    ])


def _account_line(row: dict) -> str:
    base = row.get("original_email_line") or row.get("email") or ""
    token = row.get("access_token") or ""
    totp = row.get("totp_secret") or ""
    return f"{base}----{token}----{totp}" if totp else f"{base}----{token}"


def _registered_email_line(row: dict) -> str:
    """生成注册成功邮箱 TXT 的行内容；token 由注册成功的token.txt 单独保存。"""
    return row.get("original_email_line") or row.get("email") or ""


def _sync_outlook_txt(rows: list[dict]) -> None:
    available_rows = [r for r in rows if r.get("status") == "available"]
    lines = [_outlook_line(r) for r in sorted(available_rows, key=lambda x: int(x.get("id") or 0))]
    _OUTLOOK_TXT.write_text(("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8")


def _sync_generic_api_email_txt(rows: list[dict]) -> None:
    available_rows = [r for r in rows if r.get("status") == "available"]
    lines = [_generic_api_email_line(r) for r in sorted(available_rows, key=lambda x: int(x.get("id") or 0))]
    _GENERIC_API_EMAIL_TXT.write_text(("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8")


def _sync_accounts_txt(rows: list[dict]) -> None:
    lines = [_registered_email_line(r) for r in sorted(rows, key=lambda x: int(x.get("id") or 0))]
    _ACCOUNTS_TXT.write_text(("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8")


def _sync_tokens_txt(rows: list[dict]) -> None:
    tokens = [
        r.get("access_token") or ""
        for r in sorted(rows, key=lambda x: int(x.get("id") or 0))
        if r.get("access_token")
    ]
    _TOKENS_TXT.write_text(("\n".join(tokens) + ("\n" if tokens else "")), encoding="utf-8")


def _viewer_snapshot(outlook_rows: list[dict], account_rows: list[dict]) -> dict:
    account_by_email = {
        (a.get("email") or "").lower(): a
        for a in account_rows
    }
    return {
        "generated_at": _now(),
        "accounts": [
            _decorate_account(r)
            for r in sorted(account_rows, key=lambda x: int(x.get("id") or 0), reverse=True)
        ],
        "outlook": [
            _decorate_outlook(r, account_by_email)
            for r in sorted(outlook_rows, key=lambda x: int(x.get("id") or 0), reverse=True)
        ],
        "summary": {
            "accounts": len(account_rows),
            "outlook_total": len(outlook_rows),
            "outlook_available": sum(1 for r in outlook_rows if r.get("status") == "available"),
            "outlook_used": sum(1 for r in outlook_rows if r.get("status") == "used"),
            "outlook_failed": sum(1 for r in outlook_rows if r.get("status") == "failed"),
        },
    }


def _render_static_viewer(outlook_rows: list[dict] | None = None, account_rows: list[dict] | None = None) -> Path:
    """生成可直接双击打开的静态账号查看页。"""
    outlook_rows = _load_outlook() if outlook_rows is None else outlook_rows
    account_rows = _load_accounts() if account_rows is None else account_rows
    snapshot = _viewer_snapshot(outlook_rows, account_rows)
    data_json = json.dumps(snapshot, ensure_ascii=False).replace("</", "<\\/")
    title = escape(f"账号查看器 - {snapshot['generated_at']}")
    html_text = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    :root {{
      --bg: #eef3f8;
      --surface: #ffffff;
      --soft: #f7f9fc;
      --text: #172033;
      --muted: #667085;
      --line: #d9e2ec;
      --blue: #2563eb;
      --green: #16803c;
      --red: #c2413a;
      --amber: #b7791f;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      padding: 22px 28px;
      background: #101827;
      color: #fff;
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: center;
      flex-wrap: wrap;
    }}
    h1, h2, p {{ margin: 0; }}
    h1 {{ font-size: 28px; }}
    .meta {{ margin-top: 6px; color: #b8c7d9; font-size: 13px; }}
    .stats {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .stat {{
      min-width: 116px;
      padding: 10px 12px;
      border: 1px solid rgba(255,255,255,.16);
      border-radius: 8px;
      background: rgba(255,255,255,.08);
    }}
    .stat span {{ display: block; color: #b8c7d9; font-size: 12px; }}
    .stat strong {{ display: block; margin-top: 4px; font-size: 18px; }}
    main {{ width: min(1500px, calc(100vw - 32px)); margin: 16px auto 30px; display: grid; gap: 16px; }}
    .toolbar, section {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: 0 8px 22px rgba(15,23,42,.06);
    }}
    .toolbar {{ padding: 14px; display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
    .search {{ min-width: min(520px, 100%); flex: 1; }}
    input {{
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 12px;
      font: inherit;
    }}
    .buttons {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    button {{
      min-height: 32px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      padding: 0 12px;
      font-weight: 700;
      cursor: pointer;
    }}
    button:hover {{ background: var(--soft); }}
    button.primary {{ border-color: var(--blue); background: var(--blue); color: #fff; }}
    button.good {{ border-color: #2f855a; background: #edf8f1; color: #166534; }}
    button:disabled {{ color: #98a2b3; cursor: not-allowed; background: #f2f4f7; }}
    .head {{ padding: 14px 16px; border-bottom: 1px solid var(--line); background: var(--soft); }}
    .head p {{ margin-top: 4px; color: var(--muted); font-size: 12px; }}
    .table-wrap {{ overflow: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #edf1f5; text-align: left; white-space: nowrap; vertical-align: middle; }}
    th {{ position: sticky; top: 0; background: #fbfcfe; color: #475467; z-index: 1; font-size: 12px; }}
    tr:hover td {{ background: #fbfdff; }}
    .main-cell {{ font-weight: 700; }}
    .sub-cell {{ margin-top: 3px; color: var(--muted); font-size: 12px; }}
    .mono {{ font-family: ui-monospace, "JetBrains Mono", Consolas, monospace; font-size: 12px; }}
    .muted {{ color: var(--muted); }}
    .pill {{ display: inline-flex; min-width: 48px; justify-content: center; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
    .status-available {{ color: var(--blue); background: #eef4ff; }}
    .status-used {{ color: #475467; background: #f2f4f7; }}
    .status-failed {{ color: var(--red); background: #fff0ef; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    #toast {{
      position: fixed;
      right: 18px;
      bottom: 18px;
      padding: 10px 14px;
      border-radius: 8px;
      background: #101827;
      color: #fff;
      box-shadow: 0 14px 30px rgba(15,23,42,.24);
      opacity: 0;
      transform: translateY(8px);
      pointer-events: none;
      transition: opacity .18s ease, transform .18s ease;
    }}
    #toast.show {{ opacity: 1; transform: translateY(0); }}
    @media (max-width: 820px) {{
      header {{ align-items: flex-start; }}
      .stats {{ width: 100%; }}
      .stat {{ flex: 1; }}
    }}
  </style>
</head>
<body>
<header>
  <div>
    <h1>账号查看器</h1>
    <p class="meta">静态快照，无需启动 Web Server。生成时间：<span id="generated"></span></p>
  </div>
  <div class="stats">
    <div class="stat"><span>已完成</span><strong id="statAccounts">0</strong></div>
    <div class="stat"><span>邮箱总数</span><strong id="statOutlook">0</strong></div>
    <div class="stat"><span>可用邮箱</span><strong id="statAvailable">0</strong></div>
  </div>
</header>
<main>
  <div class="toolbar">
    <div class="search"><input id="q" placeholder="搜索邮箱、token、clientId、状态"></div>
    <div class="buttons">
      <button class="primary" id="copyAllTokens">复制全部 Token</button>
      <button class="good" id="copyAllLines">复制全部整行</button>
      <button id="copyAllEmails">复制全部邮箱素材</button>
    </div>
  </div>
  <section>
    <div class="head">
      <h2>已完成账号</h2>
      <p>整行格式：邮箱----密码----clientId----邮箱刷新令牌----accessToken----totpSecret（如有）</p>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>ID</th><th>邮箱</th><th>来源</th><th>Token</th><th>备注</th><th>2FA</th><th>创建时间</th><th>操作</th></tr></thead>
        <tbody id="accountsBody"></tbody>
      </table>
    </div>
  </section>
  <section>
    <div class="head">
      <h2>邮箱素材库</h2>
      <p>原始格式：邮箱----密码----clientId----邮箱刷新令牌；注册完成后可直接复制对应 Token 或整行。</p>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>邮箱</th><th>状态</th><th>Token</th><th>导入时间</th><th>已用时间</th><th>操作</th></tr></thead>
        <tbody id="outlookBody"></tbody>
      </table>
    </div>
  </section>
</main>
<div id="toast"></div>
<script id="snapshot" type="application/json">{data_json}</script>
<script>
const SNAPSHOT = JSON.parse(document.getElementById('snapshot').textContent);
const $ = (s) => document.querySelector(s);
let copySeq = 0;
const copyStore = new Map();

function fmt(v) {{ return v == null || v === '' ? '-' : String(v); }}
function esc(v) {{
  return fmt(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}
function short(v, n = 34) {{
  const s = v || '';
  return s.length > n ? `${{s.slice(0, n)}}...` : s;
}}
function copyId(v) {{
  if (!v) return '';
  const id = `c${{++copySeq}}`;
  copyStore.set(id, v);
  return id;
}}
function btn(label, value, cls = '') {{
  const id = copyId(value);
  return `<button class="${{cls}}" data-copy-id="${{id}}" ${{id ? '' : 'disabled'}}>${{label}}</button>`;
}}
function pill(status) {{
  const map = {{ available: '可用', used: '已用', failed: '失败' }};
  const label = map[status] || status || '-';
  return `<span class="pill status-${{esc(status)}}">${{esc(label)}}</span>`;
}}
function showToast(text) {{
  const toast = $('#toast');
  toast.textContent = text;
  toast.classList.add('show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('show'), 1400);
}}
async function copyText(text) {{
  if (!text) return;
  if (navigator.clipboard && window.isSecureContext) {{
    await navigator.clipboard.writeText(text);
  }} else {{
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  }}
  showToast('已复制');
}}
function haystack(row) {{
  return Object.values(row).join('\\n').toLowerCase();
}}
function render() {{
  copyStore.clear();
  copySeq = 0;
  const q = $('#q').value.trim().toLowerCase();
  const accounts = SNAPSHOT.accounts.filter((r) => !q || haystack(r).includes(q));
  const outlook = SNAPSHOT.outlook.filter((r) => !q || haystack(r).includes(q));
  $('#generated').textContent = SNAPSHOT.generated_at;
  $('#statAccounts').textContent = SNAPSHOT.summary.accounts;
  $('#statOutlook').textContent = SNAPSHOT.summary.outlook_total;
  $('#statAvailable').textContent = SNAPSHOT.summary.outlook_available;
  $('#accountsBody').innerHTML = accounts.map((r) => `
    <tr>
      <td class="muted">#${{esc(r.id)}}</td>
      <td><div class="main-cell">${{esc(r.email)}}</div><div class="sub-cell">${{esc(r.user_name || '-')}}</div></td>
      <td>${{esc(r.email_source || '-')}}</td>
      <td><span class="mono">${{esc(short(r.access_token || '', 42))}}</span></td>
      <td title="${{esc(r.note || '')}}">${{r.note ? esc(short(r.note, 60)) : '<span class="muted">-</span>'}}</td>
      <td>${{r.totp_secret ? '已启用' : '<span class="muted">未启用</span>'}}</td>
      <td class="muted">${{esc(r.created_at || '-')}}</td>
      <td class="actions">${{btn('复制Token', r.access_token, 'primary')}} ${{btn('复制整行', r.copy_line, 'good')}}</td>
    </tr>`).join('');
  $('#outlookBody').innerHTML = outlook.map((r) => `
    <tr>
      <td><div class="main-cell">${{esc(r.email)}}</div><div class="sub-cell mono">${{esc(short(r.copy_line, 76))}}</div></td>
      <td>${{pill(r.status)}}</td>
      <td><span class="mono">${{esc(short(r.access_token || '', 36) || '未生成')}}</span></td>
      <td class="muted">${{esc(r.imported_at || r.created_at || '-')}}</td>
      <td class="muted">${{esc(r.used_at || '-')}}</td>
      <td class="actions">${{btn('复制邮箱', r.copy_line)}} ${{btn('复制Token', r.access_token, 'primary')}} ${{btn('复制整行', r.account_copy_line, 'good')}}</td>
    </tr>`).join('');
}}
document.addEventListener('click', (e) => {{
  const target = e.target.closest('[data-copy-id]');
  if (!target) return;
  copyText(copyStore.get(target.dataset.copyId));
}});
$('#q').addEventListener('input', render);
$('#copyAllTokens').addEventListener('click', () => copyText(SNAPSHOT.accounts.map((r) => r.access_token).filter(Boolean).join('\\n')));
$('#copyAllLines').addEventListener('click', () => copyText(SNAPSHOT.accounts.map((r) => r.copy_line).filter(Boolean).join('\\n')));
$('#copyAllEmails').addEventListener('click', () => copyText(SNAPSHOT.outlook.map((r) => r.copy_line).filter(Boolean).join('\\n')));
render();
</script>
</body>
</html>
"""
    tmp = _VIEWER_HTML.with_suffix(".html.tmp")
    tmp.write_text(html_text, encoding="utf-8")
    try:
        tmp.replace(_VIEWER_HTML)
        return _VIEWER_HTML
    except PermissionError:
        # Windows 下如果目标 HTML 正被浏览器或编辑器短暂占用，原子替换可能失败。
        # 先尝试直接覆盖；仍失败时写一个时间戳快照，避免注册流程被查看页刷新阻断。
        try:
            _VIEWER_HTML.write_text(html_text, encoding="utf-8")
            try:
                tmp.unlink()
            except OSError:
                pass
            return _VIEWER_HTML
        except PermissionError:
            fallback = _DATA_DIR / f"accounts_viewer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            fallback.write_text(html_text, encoding="utf-8")
            try:
                tmp.unlink()
            except OSError:
                pass
            return fallback


def _load_outlook() -> list[dict]:
    return _load_table(record_store.OUTLOOK_POOL)


def _export_outlook(rows: list[dict]) -> None:
    """兼容导出。第 4 步会改成去抖后台任务。"""
    _write_json(_OUTLOOK_JSON, rows)
    _sync_outlook_txt(rows)
    _render_static_viewer(outlook_rows=rows)


def _save_outlook(rows: list[dict]) -> None:
    _sync_table(record_store.OUTLOOK_POOL, rows)
    _export_outlook(rows)


def _load_generic_api_emails() -> list[dict]:
    return _load_table(record_store.GENERIC_API_POOL)


def _export_generic_api_emails(rows: list[dict]) -> None:
    _write_json(_GENERIC_API_EMAIL_JSON, rows)
    _sync_generic_api_email_txt(rows)


def _save_generic_api_emails(rows: list[dict]) -> None:
    for row in rows:
        row["copy_line"] = _generic_api_email_line(row)
    _sync_table(record_store.GENERIC_API_POOL, rows)
    _export_generic_api_emails(rows)


def _load_accounts() -> list[dict]:
    return _load_table(record_store.ACCOUNTS)


def _export_accounts(rows: list[dict]) -> None:
    _write_json(_ACCOUNTS_JSON, rows)
    _sync_accounts_txt(rows)
    _sync_tokens_txt(rows)
    _render_static_viewer(account_rows=rows)


def _save_accounts(rows: list[dict]) -> None:
    for row in rows:
        row["copy_line"] = _account_line(row)
    _sync_table(record_store.ACCOUNTS, rows)
    _export_accounts(rows)


def _load_jobs() -> list[dict]:
    return _load_table(record_store.JOBS)


def _export_jobs(rows: list[dict]) -> None:
    _write_json(_JOBS_JSON, rows)


def _save_jobs(rows: list[dict]) -> None:
    _sync_table(record_store.JOBS, rows)
    _export_jobs(rows)


def _save_together(*pairs) -> None:
    """把多张表的写入并进同一个事务，再统一做兼容导出。

    用于 insert_account / import_registered_email_accounts /
    recover_interrupted_registration_jobs 这三个跨集合操作：它们原先是两次独立
    落盘，中间失败会留下"账号已创建但邮箱池没标记 used"这种半完成状态。

    每个 pair 是 (spec, rows, export_fn)。
    """
    with record_store.transaction() as conn:
        for spec, rows, _export in pairs:
            _sync_table(spec, rows, conn=conn)
    for _spec, rows, export in pairs:
        if export is not None:
            export(rows)


def _find_by_email(rows: list[dict], email: str) -> dict | None:
    target = (email or "").lower()
    return next((r for r in rows if (r.get("email") or "").lower() == target), None)


def _decorate_account(row: dict) -> dict:
    out = dict(row)
    out["note"] = out.get("note") or ""
    out["note_updated_at"] = out.get("note_updated_at") or ""
    plan_status = out.get("plan_check_status")
    if plan_status in {"queued", "running"}:
        try:
            stamp_key = "plan_check_queued_at" if plan_status == "queued" else "plan_check_started_at"
            stale_after = _PLAN_CHECK_QUEUE_STALE_SECONDS if plan_status == "queued" else _PLAN_CHECK_STALE_SECONDS
            started_at = datetime.fromisoformat(str(out.get(stamp_key) or ""))
            if (datetime.now() - started_at).total_seconds() >= stale_after:
                out["plan_check_status"] = "failed"
                out["plan_check_error"] = "上次套餐查询状态已超时，可重新查询"
                out["plan_check_stale"] = True
        except (TypeError, ValueError):
            out["plan_check_status"] = "failed"
            out["plan_check_error"] = "上次套餐查询状态异常，可重新查询"
            out["plan_check_stale"] = True
    out["copy_line"] = _account_line(out)
    return out


def _account_matches_plan_filter(row: dict, plan_filter: str | None = None) -> bool:
    """账号套餐过滤。plus 表示已开通 Plus（兼容 plus/chatgpt_plus/plus_trial 等标记）。"""
    f = str(plan_filter or "").strip().lower()
    if not f or f in {"all", "any"}:
        return True
    plan = str(row.get("current_plan_type") or row.get("plan_type") or "").strip().lower()
    if f == "plus":
        # “free(可Plus试用)”/plus_trial_eligible 只是可试用，不算已开通 Plus。
        # 只有套餐字段本身是 Plus/ChatGPT Plus/plus_* 且不含 free 时才命中。
        return "plus" in plan and "free" not in plan
    if f == "free":
        return plan == "free"
    return plan == f


def _decorate_outlook(row: dict, account_by_email: dict[str, dict] | None = None) -> dict:
    out = dict(row)
    out["copy_line"] = _outlook_line(out)
    account = None
    if account_by_email is not None:
        account = account_by_email.get((out.get("email") or "").lower())
    if account:
        out["registered_account_id"] = account.get("id")
        out["access_token"] = account.get("access_token")
        out["access_token_preview"] = (
            (account.get("access_token") or "")[:40] + "..."
            if account.get("access_token")
            else ""
        )
        out["account_copy_line"] = _account_line(account)
        out["totp_secret"] = account.get("totp_secret")
    return out


def _decorate_generic_api_email(row: dict, account_by_email: dict[str, dict] | None = None) -> dict:
    out = dict(row)
    out["copy_line"] = _generic_api_email_line(out)
    out["password"] = out.get("password") or ""
    out["client_id"] = out.get("client_id") or ""
    out["refresh_token"] = out.get("refresh_token") or ""
    account = None
    if account_by_email is not None:
        account = account_by_email.get((out.get("email") or "").lower())
    if account:
        out["registered_account_id"] = account.get("id")
        out["access_token"] = account.get("access_token")
        out["access_token_preview"] = (
            (account.get("access_token") or "")[:40] + "..."
            if account.get("access_token")
            else ""
        )
        out["account_copy_line"] = _account_line(account)
        out["totp_secret"] = account.get("totp_secret")
    return out


def _get_conn() -> None:
    """兼容旧入口：初始化文件存储目录。"""
    _ensure_storage()
    return None


def _row_to_dict(row: dict | None) -> dict | None:
    return dict(row) if row is not None else None


# ============================================================
# registered_accounts
# ============================================================

def insert_account(
    *,
    email: str,
    access_token: str,
    totp_secret: str | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
    plan_type: str | None = None,
    expires_at: str | None = None,
    device_id: str | None = None,
    proxy_used: str | None = None,
    email_source: str | None = None,
    extra: dict | None = None,
    codex_status: str | None = None,   # success / failed / skipped / missing
    codex_error: str | None = None,    # 失败原因（仅 codex_status=failed 时有意义）
) -> int:
    """插入或更新注册成功账号，返回本地文件中的 id。"""
    with _LOCK:
        accounts = _load_accounts()
        outlook_rows = _load_outlook()
        existing = _find_by_email(accounts, email)
        outlook_row = _find_by_email(outlook_rows, email)
        extra_json = json.dumps(extra, ensure_ascii=False) if extra else None

        if existing is None:
            row_id = _next_id(accounts)
            row = {
                "id": row_id,
                "email": email,
                "created_at": _now(),
            }
            accounts.append(row)
        else:
            row = existing
            row_id = int(row["id"])

        row.update({
            "access_token": access_token,
            "totp_secret": totp_secret if totp_secret is not None else row.get("totp_secret"),
            "user_id": user_id if user_id is not None else row.get("user_id"),
            "user_name": user_name if user_name is not None else row.get("user_name"),
            "plan_type": plan_type if plan_type is not None else row.get("plan_type"),
            "expires_at": expires_at if expires_at is not None else row.get("expires_at"),
            "device_id": device_id if device_id is not None else row.get("device_id"),
            "proxy_used": proxy_used if proxy_used is not None else row.get("proxy_used"),
            "email_source": email_source if email_source is not None else row.get("email_source"),
            "extra_json": extra_json if extra_json is not None else row.get("extra_json"),
            "codex_status": codex_status if codex_status is not None else row.get("codex_status"),
            "codex_error": codex_error if codex_error is not None else row.get("codex_error"),
            "updated_at": _now(),
        })
        if access_token:
            # expires_at 是 ChatGPT Session 到期时间；AT 自身到期时间来自 JWT exp，
            # 两者分开保存，避免页面和刷新调度误判。
            from core.chatgpt_plan import token_claims
            claims = token_claims(access_token)
            row["token_expires_at"] = claims.get("token_expires_at")
            row["token_expired"] = claims.get("token_expired")

        if outlook_row:
            row["password"] = outlook_row.get("password")
            row["client_id"] = outlook_row.get("client_id")
            row["refresh_token"] = outlook_row.get("refresh_token")
            row["original_email_line"] = _outlook_line(outlook_row)
            outlook_row["status"] = "used"
            outlook_row["used_at"] = outlook_row.get("used_at") or _now()
            outlook_row["registered_account_id"] = row_id
            outlook_row["access_token"] = access_token
            outlook_row["completed_at"] = _now()
            if totp_secret:
                outlook_row["totp_secret"] = totp_secret

        row["copy_line"] = _account_line(row)
        _save_accounts(accounts)
        _save_outlook(outlook_rows)
        return row_id


def update_account_codex_status(email: str, codex_status: str, codex_error: str | None = None) -> bool:
    """
    单独更新某账号的 codex_status / codex_error（手动补跑 Codex 时用）。
    返回是否找到该账号。
    """
    with _LOCK:
        accounts = _load_accounts()
        row = _find_by_email(accounts, email)
        if row is None:
            return False
        row["codex_status"] = codex_status
        row["codex_error"] = codex_error
        row["updated_at"] = _now()
        _save_accounts(accounts)
        return True


def update_account_token_metadata(acc_id: int, access_token: str) -> bool:
    """只同步当前 AT 的 JWT 到期信息，不改动账号状态或 Token 内容。"""
    from core.chatgpt_plan import token_claims
    claims = token_claims(access_token)
    with _LOCK:
        accounts = _load_accounts()
        row = next((r for r in accounts if int(r.get("id") or 0) == int(acc_id)), None)
        if row is None or str(row.get("access_token") or "").strip() != str(access_token or "").strip():
            return False
        expires_at = claims.get("token_expires_at")
        expired = claims.get("token_expired")
        if row.get("token_expires_at") == expires_at and row.get("token_expired") == expired:
            return True
        row["token_expires_at"] = expires_at
        row["token_expired"] = expired
        row["updated_at"] = _now()
        _save_accounts(accounts)
        return True


def sync_account_token_metadata(items: list[tuple[int, str]]) -> int:
    """批量回填 AT 到期信息，只在内容变化时写一次账号文件。"""
    from core.chatgpt_plan import token_claims
    tokens = {int(acc_id): str(token or "").strip() for acc_id, token in items if str(token or "").strip()}
    if not tokens:
        return 0
    with _LOCK:
        accounts = _load_accounts()
        changed = 0
        for row in accounts:
            acc_id = int(row.get("id") or 0)
            token = tokens.get(acc_id)
            if not token or str(row.get("access_token") or "").strip() != token:
                continue
            claims = token_claims(token)
            expires_at = claims.get("token_expires_at")
            expired = claims.get("token_expired")
            if row.get("token_expires_at") == expires_at and row.get("token_expired") == expired:
                continue
            row["token_expires_at"] = expires_at
            row["token_expired"] = expired
            row["updated_at"] = _now()
            changed += 1
        if changed:
            _save_accounts(accounts)
        return changed


def _stage_claim_guard(prefix: str, *, require_alive: bool = False) -> tuple[str, list]:
    """构造"未被占用，或占用已超时"的 SQL 判据。

    改造前这段是"读出来判断状态，再写回去"，两个进程会同时读到 idle 然后都以为
    抢到了——`threading.RLock` 只在进程内有效，而 CLI 与 WebUI 是两个进程。
    改成条件 UPDATE 后，判据和写入在同一条语句里，由数据库保证互斥。

    时间戳是 ISO 字符串，字典序即时间序，可以直接比较。缺失、空串或不像时间戳
    的值一律视为已超时——这保留了原实现"解析失败就放行"的语义，否则一行脏数据
    会让这个账号永远无法再被领取。
    """
    now = datetime.now()
    queue_before = (now - timedelta(seconds=_PLAN_CHECK_QUEUE_STALE_SECONDS)).isoformat(timespec="seconds")
    run_before = (now - timedelta(seconds=_PLAN_CHECK_STALE_SECONDS)).isoformat(timespec="seconds")
    status = f'"{prefix}_status"'
    guard = (
        f"(COALESCE({status}, '') NOT IN ('queued', 'running')"
        f" OR ({status} = 'queued' AND (COALESCE(data->>'{prefix}_queued_at', '') !~ '^[0-9]{{4}}-'"
        f"      OR data->>'{prefix}_queued_at' < %s))"
        f" OR ({status} = 'running' AND (COALESCE(data->>'{prefix}_started_at', '') !~ '^[0-9]{{4}}-'"
        f"      OR data->>'{prefix}_started_at' < %s)))"
    )
    params = [queue_before, run_before]
    if require_alive:
        guard = f"deactivated = FALSE AND {guard}"
    return guard, params


def _claim_account_stage(acc_id: int, prefix: str, changes: dict, *, require_alive: bool = False) -> bool:
    guard, params = _stage_claim_guard(prefix, require_alive=require_alive)
    return record_store.claim_row(
        record_store.ACCOUNTS, int(acc_id),
        changes=changes, guard=guard, guard_params=params,
    )


def _mark_account_stage_running(acc_id: int, prefix: str, changes: dict) -> bool:
    """仅当该阶段确实处于 queued/running 时才置为 running。"""
    return record_store.claim_row(
        record_store.ACCOUNTS, int(acc_id),
        changes=changes,
        guard=f"COALESCE(\"{prefix}_status\", '') IN ('queued', 'running')",
    )


def claim_account_plan_check(
    acc_id: int | None = None,
    email: str | None = None,
    trigger: str = "manual",
) -> bool:
    """原子占用账号的套餐查询；已有未超时查询时返回 False。"""
    if acc_id is None:
        row = get_account_by_email(email or "")
        if row is None:
            return False
        acc_id = int(row["id"])
    now = _now()
    return _claim_account_stage(acc_id, "plan_check", {
        "plan_check_status": "queued",
        "plan_check_trigger": str(trigger or "manual"),
        "plan_check_queued_at": now,
        "plan_check_started_at": None,
        "plan_check_completed_at": None,
        "plan_check_error": None,
        "updated_at": now,
    })


def mark_account_plan_check_running(acc_id: int) -> bool:
    """把已排队的套餐查询标记为执行中。"""
    now = _now()
    return _mark_account_stage_running(acc_id, "plan_check", {
        "plan_check_status": "running",
        "plan_check_started_at": now,
        "plan_check_error": None,
        "updated_at": now,
    })


def recover_interrupted_plan_checks() -> int:
    """服务启动时把上次进程遗留的内存队列状态恢复为可重试失败。"""
    with _LOCK:
        accounts = _load_accounts()
        recovered = 0
        now = _now()
        for row in accounts:
            if row.get("plan_check_status") not in {"queued", "running"}:
                continue
            row["plan_check_status"] = "failed"
            row["plan_check_ok"] = False
            row["plan_check_error"] = "WebUI 重启导致套餐查询中断，请重新查询"
            row["plan_check_completed_at"] = now
            row["updated_at"] = now
            recovered += 1
        if recovered:
            _save_accounts(accounts)
        return recovered


def update_account_plan_check(acc_id: int | None = None, email: str | None = None, result: dict | None = None) -> bool:
    """更新账号套餐/Plus 试用资格查询结果。"""
    result = result or {}
    with _LOCK:
        accounts = _load_accounts()
        target_email = (email or "").lower()
        row = next((
            r for r in accounts
            if (acc_id is not None and int(r.get("id") or 0) == int(acc_id))
            or (target_email and (r.get("email") or "").lower() == target_email)
        ), None)
        if row is None:
            return False

        ok = bool(result.get("ok"))
        row["plan_check_status"] = "success" if ok else "failed"
        row["plan_check_ok"] = ok
        row["plan_checked_at"] = result.get("checked_at") or _now()
        row["plan_check_completed_at"] = _now()
        row["plan_check_http_status"] = result.get("http_status")
        row["plan_check_error"] = None if ok else result.get("error")

        if result.get("account_id"):
            row["account_id"] = result.get("account_id")
        # 查询失败只更新本次错误和网络信息，不覆盖上一次成功拿到的套餐、
        # 试用资格、优惠及有效期，避免临时网络故障把真实权益清空。
        if ok:
            if result.get("current_plan_type"):
                row["current_plan_type"] = result.get("current_plan_type")
                row["plan_type"] = result.get("current_plan_type")
            if result.get("subscription_plan") is not None:
                row["subscription_plan"] = result.get("subscription_plan")
            if result.get("has_active_subscription") is not None:
                row["has_active_subscription"] = bool(result.get("has_active_subscription"))
            if result.get("expires_at") is not None:
                row["plan_expires_at"] = result.get("expires_at")
            if result.get("renews_at") is not None:
                row["plan_renews_at"] = result.get("renews_at")
            if result.get("cancels_at") is not None:
                row["plan_cancels_at"] = result.get("cancels_at")
            if result.get("billing_period") is not None:
                row["billing_period"] = result.get("billing_period")
            if result.get("billing_currency") is not None:
                row["billing_currency"] = result.get("billing_currency")
            if result.get("is_delinquent") is not None:
                row["is_delinquent"] = bool(result.get("is_delinquent"))
            for _k in (
                "discount_type",
                "discount_amount",
                "discount_duration_num_periods",
                "discount_expires_at",
                "discount_cancellation_policy",
                "discount_promo_campaign_id",
                "last_purchase_origin_platform",
                "last_will_renew",
            ):
                if result.get(_k) is not None:
                    row[_k] = result.get(_k)

            row["plus_trial_eligible"] = bool(result.get("plus_trial_eligible"))
            row["plus_trial_campaign_id"] = result.get("plus_trial_campaign_id")
            row["plus_trial_title"] = result.get("plus_trial_title")
            row["plus_trial_discount_percentage"] = result.get("plus_trial_discount_percentage")
            row["plus_trial_duration_num_periods"] = result.get("plus_trial_duration_num_periods")
            row["plus_trial_duration_period"] = result.get("plus_trial_duration_period")
            row["eligible_offer_ids"] = result.get("eligible_offer_ids") or []
            row["plan_last_success_at"] = result.get("checked_at") or _now()
            row["plan_last_success_result_json"] = json.dumps(result, ensure_ascii=False)
        row["plan_check_proxy_mode"] = result.get("proxy_mode")
        row["plan_check_network_route"] = result.get("network_route")
        row["plan_check_proxy_used"] = result.get("proxy_used")
        row["plan_check_proxy_fallback_reason"] = result.get("proxy_fallback_reason")
        row["token_expired"] = result.get("token_expired")
        row["token_expires_at"] = result.get("token_expires_at")
        row["plan_check_result_json"] = json.dumps(result, ensure_ascii=False)
        row["updated_at"] = _now()
        _save_accounts(accounts)
        return True


def claim_account_extract(acc_id: int, trigger: str = "manual", link_type: str = "pix") -> bool:
    """原子占用账号提链任务；已有未超时任务时返回 False。"""
    now = _now()
    return _claim_account_stage(acc_id, "extract_link", {
        "extract_link_status": "queued",
        "extract_link_ok": False,
        "extract_link_trigger": str(trigger or "manual"),
        "extract_link_type": str(link_type or "pix").lower(),
        "extract_link_queued_at": now,
        "extract_link_started_at": None,
        "extract_link_completed_at": None,
        "extract_link_error": None,
        "extract_link_message": "已入队",
        "updated_at": now,
    })


def mark_account_extract_running(acc_id: int) -> bool:
    """把提链任务标记为运行中。"""
    now = _now()
    return _mark_account_stage_running(acc_id, "extract_link", {
        "extract_link_status": "running",
        "extract_link_started_at": now,
        "extract_link_error": None,
        "extract_link_message": "任务运行中",
        "updated_at": now,
    })


def update_account_extract(acc_id: int, result: dict | None = None) -> bool:
    """更新账号提链任务结果/进度。"""
    result = result or {}
    with _LOCK:
        accounts = _load_accounts()
        row = next((r for r in accounts if int(r.get("id") or 0) == int(acc_id)), None)
        if row is None:
            return False
        status = str(result.get("status") or ("success" if result.get("ok") else "failed"))
        ok = bool(result.get("ok")) and status == "success"
        row["extract_link_status"] = status
        row["extract_link_ok"] = ok
        row["extract_link_checked_at"] = result.get("checked_at") or _now()
        if status in {"success", "failed", "stopped"}:
            row["extract_link_completed_at"] = _now()
        row["extract_link_error"] = None if ok or status == "running" else result.get("error")
        if result.get("message") is not None:
            row["extract_link_message"] = result.get("message")
        if result.get("job_id") is not None:
            row["extract_link_job_id"] = result.get("job_id")
        if result.get("link_type") is not None:
            row["extract_link_type"] = result.get("link_type")
        if result.get("cdk_remaining") is not None:
            row["extract_link_cdk_remaining"] = result.get("cdk_remaining")
        payload = result.get("result") if isinstance(result.get("result"), dict) else {}
        if payload:
            row["extract_link_long_url"] = payload.get("long_url")
            row["extract_link_copy_paste"] = payload.get("copy_paste")
            row["extract_link_image_url_png"] = payload.get("image_url_png")
            row["extract_link_image_url_svg"] = payload.get("image_url_svg")
            row["extract_link_payment_method"] = payload.get("payment_method")
            row["extract_link_payment_link_type"] = payload.get("payment_link_type")
            row["extract_link_expires_at"] = payload.get("expires_at")
            if payload.get("cdk_remaining") is not None:
                row["extract_link_cdk_remaining"] = payload.get("cdk_remaining")
            row["extract_link_result_json"] = json.dumps(payload, ensure_ascii=False)
        row["updated_at"] = _now()
        _save_accounts(accounts)
        return True


def recover_interrupted_extract_links() -> int:
    """服务启动时恢复上次进程中断的提链状态。"""
    with _LOCK:
        accounts = _load_accounts()
        recovered = 0
        now = _now()
        for row in accounts:
            if row.get("extract_link_status") not in {"queued", "running"}:
                continue
            row["extract_link_status"] = "failed"
            row["extract_link_ok"] = False
            row["extract_link_error"] = "WebUI 重启导致提链任务中断，请重新提链"
            row["extract_link_completed_at"] = now
            row["updated_at"] = now
            recovered += 1
        if recovered:
            _save_accounts(accounts)
        return recovered


def _account_matches_query(row: dict, q: str | None) -> bool:
    q = str(q or "").strip().lower()
    if not q:
        return True
    try:
        return q in "\n".join(str(v) for v in row.values()).lower()
    except Exception:
        return False


def _parse_iso_dt(value: str | None, end_of_day: bool = False) -> datetime | None:
    """宽松解析 ISO 日期/时间字符串；支持 YYYY-MM-DD 或完整 ISO；解析失败返回 None。

    end_of_day=True 时，纯日期（YYYY-MM-DD）按当天 23:59:59.999999 解析，
    用于 date_to 过滤（保证包含截止当天）；完整时间串原样返回。
    """
    if not value:
        return None
    text = str(value).strip()
    try:
        if len(text) == 10 and text[4] == "-":
            if end_of_day:
                return datetime.fromisoformat(text + "T23:59:59.999999")
            return datetime.fromisoformat(text + "T00:00:00")
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _filtered_decorated_accounts(archived: str | bool | None = False, plan_filter: str | None = None, q: str | None = None, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    rows = _load_accounts()
    if archived in (True, "1", "true", "yes", "only"):
        rows = [r for r in rows if bool(r.get("archived"))]
    elif archived in ("all", "include"):
        pass
    else:
        rows = [r for r in rows if not bool(r.get("archived"))]
    decorated = [_decorate_account(r) for r in rows]
    decorated = [r for r in decorated if _account_matches_plan_filter(r, plan_filter)]
    decorated = [r for r in decorated if _account_matches_query(r, q)]
    # 按创建时间筛选（date_from/date_to 为 ISO 字符串或 YYYY-MM-DD）
    if date_from or date_to:
        d_from = _parse_iso_dt(date_from)
        d_to = _parse_iso_dt(date_to, end_of_day=True)
        if d_from or d_to:
            filtered = []
            for r in decorated:
                ct = _parse_iso_dt(str(r.get("created_at") or ""))
                if ct is None:
                    continue
                if d_from and ct < d_from:
                    continue
                if d_to and ct > d_to:
                    continue
                filtered.append(r)
            decorated = filtered
    return sorted(decorated, key=lambda x: int(x.get("id") or 0), reverse=True)


def list_account_plan_check_statuses(limit: int = 5000, offset: int = 0, archived: str | bool | None = False, plan_filter: str | None = None, q: str | None = None) -> dict:
    """返回不含 Token/邮箱密码的套餐查询轻量状态快照。"""
    fields = (
        "id", "email", "archived",
        "plan_type", "current_plan_type", "plus_trial_eligible",
        "plan_check_status", "plan_check_ok", "plan_check_error",
        "plan_check_trigger", "plan_check_queued_at", "plan_check_started_at",
        "plan_check_completed_at", "plan_checked_at", "plan_last_success_at",
        "plan_check_network_route", "plan_check_proxy_used", "plan_check_proxy_fallback_reason",
        "expires_at", "plan_expires_at", "plan_renews_at", "renews_at",
        "billing_period", "billing_currency", "discount_amount", "discount_type",
        "discount_expires_at", "discount_promo_campaign_id",
        "extract_link_status", "extract_link_ok", "extract_link_type",
        "extract_link_message", "extract_link_error",
        "extract_link_long_url", "extract_link_copy_paste",
        "extract_link_image_url_png", "extract_link_image_url_svg",
        "extract_link_expires_at",
        "codex_status", "codex_error",
    )
    with _LOCK:
        all_rows = _filtered_decorated_accounts(archived=archived, plan_filter=plan_filter, q=q)
        total = len(all_rows)
        limit = max(1, int(limit))
        offset = max(0, int(offset or 0))
        rows = all_rows[offset: offset + limit]
        items = []
        for row in rows:
            item = {"id": row.get("id"), "email": row.get("email")}
            for key in fields:
                value = row.get(key)
                if key in ("id", "email"):
                    continue
                if value is not None and value != "":
                    item[key] = value
            plan = str(row.get("current_plan_type") or row.get("plan_type") or "").lower()
            if not any(x in plan for x in ("plus", "pro", "team", "go")):
                for expire_key in ("expires_at", "plan_expires_at", "plan_renews_at", "renews_at"):
                    item.pop(expire_key, None)
            item["has_access_token"] = bool(str(row.get("access_token") or "").strip())
            items.append(item)
        latest = max((str(row.get("updated_at") or "") for row in all_rows), default="")
        # updated_at 目前只有秒级精度；一次快速查询可能在同一秒内完成
        # queued -> running -> success/failed，导致 revision 不变，前端跳过合并状态，
        # 页面就会一直停在“查询中”。把轻量状态本身纳入签名，保证状态变化可被轮询发现。
        revision_payload = json.dumps(
            [
                {
                    "id": row.get("id"),
                    "updated_at": row.get("updated_at"),
                    "plan_check_status": row.get("plan_check_status"),
                    "plan_check_ok": row.get("plan_check_ok"),
                    "plan_check_error": row.get("plan_check_error"),
                    "current_plan_type": row.get("current_plan_type"),
                    "plan_type": row.get("plan_type"),
                    "plus_trial_eligible": row.get("plus_trial_eligible"),
                    "extract_link_status": row.get("extract_link_status"),
                    "codex_status": row.get("codex_status"),
                }
                for row in all_rows
            ],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        revision_sig = hashlib.sha1(revision_payload.encode("utf-8")).hexdigest()[:12]
        return {"items": items, "total": total, "offset": offset, "limit": limit, "revision": f"{total}:{latest}:{revision_sig}"}


def list_accounts(limit: int = 500, offset: int = 0, archived: str | bool | None = False, plan_filter: str | None = None, q: str | None = None, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    with _LOCK:
        rows = _filtered_decorated_accounts(archived=archived, plan_filter=plan_filter, q=q, date_from=date_from, date_to=date_to)
        return rows[max(0, int(offset or 0)): max(0, int(offset or 0)) + max(1, int(limit))]


def list_accounts_page(limit: int = 50, offset: int = 0, archived: str | bool | None = False, plan_filter: str | None = None, q: str | None = None, date_from: str | None = None, date_to: str | None = None) -> dict:
    with _LOCK:
        rows = _filtered_decorated_accounts(archived=archived, plan_filter=plan_filter, q=q, date_from=date_from, date_to=date_to)
        total = len(rows)
        limit = max(1, int(limit))
        offset = max(0, int(offset or 0))
        items = rows[offset: offset + limit]
        latest = max((str(row.get("updated_at") or "") for row in rows), default="")
        return {"items": items, "total": total, "offset": offset, "limit": limit, "revision": f"{total}:{latest}"}


def get_account(acc_id: int) -> dict | None:
    with _LOCK:
        row = next((r for r in _load_accounts() if int(r.get("id") or 0) == int(acc_id)), None)
        return _decorate_account(row) if row else None


def get_account_by_email(email: str) -> dict | None:
    with _LOCK:
        row = _find_by_email(_load_accounts(), email)
        return _decorate_account(row) if row else None


def update_account_note(acc_id: int, note: str) -> bool:
    """更新单个已注册账号备注。note 为空字符串时表示清空备注。"""
    with _LOCK:
        rows = _load_accounts()
        row = next((r for r in rows if int(r.get("id") or 0) == int(acc_id)), None)
        if row is None:
            return False
        now = _now()
        row["note"] = str(note or "")
        row["note_updated_at"] = now
        row["updated_at"] = now
        _save_accounts(rows)
        return True


def update_account_registration_proxy(
    acc_id: int,
    *,
    provider: str | None = None,
    region: str | None = None,
) -> bool:
    """保存账号注册时的代理来源和实际出口国家，供后续账号功能按地区申请新租约。"""
    with _LOCK:
        accounts = _load_accounts()
        row = next((r for r in accounts if int(r.get("id") or 0) == int(acc_id)), None)
        if row is None:
            return False
        if provider is not None:
            row["registration_proxy_provider"] = str(provider or "").strip() or None
        if region is not None:
            normalized = str(region or "").strip().upper()
            row["registration_proxy_region"] = normalized if len(normalized) == 2 else None
        row["updated_at"] = _now()
        _save_accounts(accounts)
        return True


def backfill_account_registration_proxy_context() -> int:
    """从历史成功注册任务补齐账号的代理来源/实际国家；已有值不覆盖。"""
    with _LOCK:
        accounts = _load_accounts()
        jobs = sorted(_load_jobs(), key=lambda r: int(r.get("id") or 0), reverse=True)
        changed = 0
        for row in accounts:
            if row.get("registration_proxy_provider") and row.get("registration_proxy_region"):
                continue
            account_id = int(row.get("id") or 0)
            email = str(row.get("email") or "").strip().lower()
            job = next((
                item for item in jobs
                if (
                    (account_id and int(item.get("account_id") or 0) == account_id)
                    or (email and str(item.get("email") or "").strip().lower() == email)
                )
                and (
                    str(item.get("proxy_provider") or "").strip()
                    or len(str(item.get("proxy_region") or "").strip()) == 2
                )
            ), None)
            if not job:
                continue
            provider = str(job.get("proxy_provider") or "").strip()
            region = str(job.get("proxy_region") or "").strip().upper()
            touched = False
            if not row.get("registration_proxy_provider") and provider:
                row["registration_proxy_provider"] = provider
                touched = True
            if not row.get("registration_proxy_region") and len(region) == 2:
                row["registration_proxy_region"] = region
                touched = True
            if touched:
                row["updated_at"] = _now()
                changed += 1
        if changed:
            _save_accounts(accounts)
        return changed


def update_account_deactivation_mail(acc_id: int, result: dict | None = None) -> bool:
    """保存封号邮件扫描状态，不读取或修改 OAuth Token。"""
    result = result or {}
    with _LOCK:
        rows = _load_accounts()
        row = next((r for r in rows if int(r.get("id") or 0) == int(acc_id)), None)
        if row is None:
            return False
        now = _now()
        status = str(result.get("status") or "failed")
        row["deactivation_mail_scan_status"] = status
        row["deactivation_mail_scan_trigger"] = str(result.get("trigger") or "")
        if status == "queued":
            row["deactivation_mail_scan_queued_at"] = now
        elif status == "running":
            row["deactivation_mail_scan_started_at"] = now
        elif status == "success":
            detected = bool(result.get("detected"))
            # 已确认的封号通知是持久证据，后续缩短回溯窗口不能把它清掉。
            row["deactivation_mail_detected"] = bool(row.get("deactivation_mail_detected")) or detected
            row["deactivation_mail_checked_at"] = result.get("checked_at") or now
            row["deactivation_mail_error"] = None
            if detected:
                row["deactivation_mail_received_at"] = result.get("received_at") or ""
                row["deactivation_mail_subject"] = str(result.get("subject") or "")[:300]
                row["deactivation_mail_sender"] = str(result.get("sender") or "")[:200]
                row["deactivation_mail_message_id"] = str(result.get("message_id") or "")[:300]
                row["deactivation_mail_confidence"] = str(result.get("confidence") or "high")
        elif status in {"failed", "unsupported"}:
            row["deactivation_mail_checked_at"] = result.get("checked_at") or now
            row["deactivation_mail_error"] = str(result.get("error") or "")[:500]
        row["updated_at"] = now
        _save_accounts(rows)
        return True


def update_account_liveness(acc_id: int, result: dict | None = None) -> bool:
    """写回账号查活结果；成功时同步刷新最新 access_token 和账号基础信息。"""
    result = result or {}
    with _LOCK:
        rows = _load_accounts()
        row = next((r for r in rows if int(r.get("id") or 0) == int(acc_id)), None)
        if row is None:
            return False

        now = _now()
        ok = bool(result.get("ok"))
        status = str(result.get("status") or ("live" if ok else "failed"))
        row["live_check_status"] = status
        row["live_check_ok"] = ok
        row["live_checked_at"] = result.get("checked_at") or now
        row["live_check_error"] = None if ok else result.get("error")
        row["updated_at"] = now

        if status == "deactivated":
            row["account_status"] = "deactivated"
            row["account_status_reason"] = result.get("error") or "账号已删除/停用/封禁"
            row["account_status_at"] = result.get("checked_at") or now
            row["codex_status"] = "deactivated"
            row["codex_error"] = result.get("error") or "账号已删除/停用/封禁"

        if ok:
            token = str(result.get("access_token") or "").strip()
            if token:
                row["access_token"] = token
                from core.chatgpt_plan import token_claims
                claims = token_claims(token)
                row["token_expires_at"] = claims.get("token_expires_at")
                row["token_expired"] = claims.get("token_expired")
            session = result.get("session") or {}
            user = session.get("user") or {}
            account = session.get("account") or {}
            if user.get("id"):
                row["user_id"] = user.get("id")
            if user.get("name") is not None:
                row["user_name"] = user.get("name")
            if account.get("planType"):
                row["plan_type"] = account.get("planType")
            if session.get("expires"):
                row["expires_at"] = session.get("expires")
            if result.get("device_id"):
                row["device_id"] = result.get("device_id")
            if result.get("proxy_used"):
                row["live_check_proxy_used"] = result.get("proxy_used")
            row["live_check_error"] = None

        row["copy_line"] = _account_line(row)
        _save_accounts(rows)
        return True


def account_is_deactivated(account: dict | None) -> bool:
    """判断账号是否已被明确标记为封号/停用；历史记录缺字段时视为正常。"""
    return str((account or {}).get("account_status") or "").strip().lower() == "deactivated"


def claim_account_live_check(acc_id: int, trigger: str = "manual") -> bool:
    """原子占用账号查活任务；已有未超时任务或账号已封时返回 False。"""
    now = _now()
    return _claim_account_stage(acc_id, "live_check", {
        "live_check_status": "queued",
        "live_check_ok": False,
        "live_check_trigger": str(trigger or "manual"),
        "live_check_queued_at": now,
        "live_check_started_at": None,
        "live_checked_at": None,
        "live_check_error": None,
        "updated_at": now,
    }, require_alive=True)


def recover_interrupted_live_checks() -> int:
    """服务启动时恢复上次进程中断的查活状态，避免 queued/running 卡死。"""
    with _LOCK:
        rows = _load_accounts()
        recovered = 0
        now = _now()
        for row in rows:
            if row.get("live_check_status") not in {"queued", "running"}:
                continue
            row["live_check_status"] = "failed"
            row["live_check_ok"] = False
            row["live_check_error"] = "WebUI 重启或任务异常中断，请重新查活"
            row["live_checked_at"] = now
            row["updated_at"] = now
            recovered += 1
        if recovered:
            _save_accounts(rows)
        return recovered


def mark_account_live_check_running(acc_id: int) -> bool:
    """把账号查活任务标记为运行中。"""
    now = _now()
    return _mark_account_stage_running(acc_id, "live_check", {
        "live_check_status": "running",
        "live_check_started_at": now,
        "live_check_error": None,
        "updated_at": now,
    })


def update_accounts_note(account_ids: list[int] | None, note: str) -> tuple[list[dict], list[dict]]:
    """
    批量更新已注册账号备注。
    返回 (updated, skipped)，updated/skipped 元素含 id/email。
    """
    ids = {int(x) for x in (account_ids or []) if str(x).strip().lstrip("-").isdigit()}
    updated: list[dict] = []
    skipped: list[dict] = []
    with _LOCK:
        rows = _load_accounts()
        seen_ids: set[int] = set()
        now = _now()
        text = str(note or "")
        for row in rows:
            row_id = int(row.get("id") or 0)
            if row_id not in ids:
                continue
            row["note"] = text
            row["note_updated_at"] = now
            row["updated_at"] = now
            updated.append({"id": row_id, "email": row.get("email"), "note": text, "note_updated_at": now})
            seen_ids.add(row_id)
        for item in ids - seen_ids:
            skipped.append({"id": item, "reason": "账号不存在"})
        if updated:
            _save_accounts(rows)
    return updated, skipped


def archive_account(acc_id: int, archived: bool = True) -> bool:
    """归档/取消归档单个已注册账号。归档不会删除 token，只影响默认账号列表查询。"""
    with _LOCK:
        rows = _load_accounts()
        row = next((r for r in rows if int(r.get("id") or 0) == int(acc_id)), None)
        if row is None:
            return False
        now = _now()
        row["archived"] = bool(archived)
        row["archived_at"] = now if archived else None
        row["updated_at"] = now
        _save_accounts(rows)
        return True


def archive_accounts(account_ids: list[int] | None, archived: bool = True) -> tuple[list[dict], list[dict]]:
    """批量归档/取消归档账号。返回 (updated, skipped)。"""
    ids = {int(x) for x in (account_ids or []) if str(x).strip().lstrip("-").isdigit()}
    updated: list[dict] = []
    skipped: list[dict] = []
    with _LOCK:
        rows = _load_accounts()
        seen_ids: set[int] = set()
        now = _now()
        for row in rows:
            row_id = int(row.get("id") or 0)
            if row_id not in ids:
                continue
            row["archived"] = bool(archived)
            row["archived_at"] = now if archived else None
            row["updated_at"] = now
            updated.append({"id": row_id, "email": row.get("email"), "archived": bool(archived), "archived_at": row.get("archived_at")})
            seen_ids.add(row_id)
        for item in ids - seen_ids:
            skipped.append({"id": item, "reason": "账号不存在"})
        if updated:
            _save_accounts(rows)
    return updated, skipped


def count_accounts() -> int:
    with _LOCK:
        return len(_load_accounts())


def delete_account(acc_id: int | None = None, email: str | None = None) -> bool:
    """删除一个已注册账号记录，并同步刷新 注册成功的邮箱.txt / token.txt / 静态查看页。"""
    with _LOCK:
        rows = _load_accounts()
        target_email = (email or "").lower()
        new_rows = []
        deleted = False
        for row in rows:
            match_id = acc_id is not None and int(row.get("id") or 0) == int(acc_id)
            match_email = bool(target_email) and (row.get("email") or "").lower() == target_email
            if match_id or match_email:
                deleted = True
                continue
            new_rows.append(row)
        if not deleted:
            return False
        _save_accounts(new_rows)
        return True


def delete_accounts(account_ids: list[int] | None = None, emails: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    """
    批量删除已注册账号。
    返回 (deleted, skipped)，deleted 元素含 id/email。
    """
    ids = {int(x) for x in (account_ids or []) if str(x).strip().isdigit()}
    email_set = {(e or "").lower() for e in (emails or []) if e}
    deleted: list[dict] = []
    skipped: list[dict] = []
    with _LOCK:
        rows = _load_accounts()
        new_rows = []
        seen_ids: set[int] = set()
        seen_emails: set[str] = set()
        for row in rows:
            row_id = int(row.get("id") or 0)
            row_email = (row.get("email") or "").lower()
            if row_id in ids or row_email in email_set:
                deleted.append({"id": row_id, "email": row.get("email")})
                seen_ids.add(row_id)
                seen_emails.add(row_email)
                continue
            new_rows.append(row)
        for item in ids - seen_ids:
            skipped.append({"id": item, "reason": "账号不存在"})
        for item in email_set - seen_emails:
            skipped.append({"email": item, "reason": "账号不存在"})
        if deleted:
            _save_accounts(new_rows)
    return deleted, skipped


# ============================================================
# outlook_pool
# ============================================================

def import_outlook_accounts(records: list[dict]) -> tuple[int, int]:
    """
    批量导入 Outlook 账号。
    records 元素：{email, password, client_id, refresh_token}
    返回 (新增数, 跳过数)。
    """
    with _LOCK:
        rows = _load_outlook()
        inserted = skipped = 0
        for raw in records:
            email = (raw.get("email") or "").strip()
            if not email:
                skipped += 1
                continue
            if _find_by_email(rows, email):
                skipped += 1
                continue
            row = {
                "id": _next_id(rows),
                "email": email,
                "password": (raw.get("password") or "").strip(),
                "client_id": (raw.get("client_id") or raw.get("clientId") or "").strip(),
                "refresh_token": (raw.get("refresh_token") or raw.get("refreshToken") or "").strip(),
                "status": "available",
                "used_at": None,
                "note": None,
                "imported_at": _now(),
            }
            row["copy_line"] = _outlook_line(row)
            rows.append(row)
            inserted += 1
        _save_outlook(rows)
        return inserted, skipped


def import_registered_email_accounts(records: list[dict], source: str | None) -> tuple[int, int]:
    """
    把邮箱素材直接导入为“已注册成功账号”，用于跳过注册、直接在账号页补跑 Codex 授权。

    source:
      - outlook: records 元素 {email,password,client_id,refresh_token[,access_token,totp_secret]}
      - generic_api: records 元素 {email,code_url[,access_token,totp_secret]}

    返回 (新增账号数, 跳过数)。已存在账号会跳过；邮箱池中已存在的素材会复用并标记 used。
    """
    source = (source or "").strip().lower()
    if source not in ("outlook", "generic_api"):
        raise ValueError("source 必须显式传入 outlook / generic_api")

    with _LOCK:
        accounts = _load_accounts()
        outlook_rows = _load_outlook()
        generic_rows = _load_generic_api_emails()
        inserted = skipped = 0

        for raw in records:
            email = (raw.get("email") or "").strip()
            if not email:
                skipped += 1
                continue
            if _find_by_email(accounts, email):
                skipped += 1
                continue

            now = _now()
            original_line = email
            pool_row = None

            if source == "generic_api":
                code_url = (raw.get("code_url") or raw.get("url") or "").strip()
                if not code_url:
                    skipped += 1
                    continue
                pool_row = _find_by_email(generic_rows, email)
                if pool_row is None:
                    pool_row = {
                        "id": _next_id(generic_rows),
                        "email": email,
                        "code_url": code_url,
                        "status": "used",
                        "used_at": now,
                        "note": "导入为已注册账号，用于 Codex 授权",
                        "imported_at": now,
                    }
                    generic_rows.append(pool_row)
                else:
                    pool_row["code_url"] = code_url or pool_row.get("code_url")
                pool_row["status"] = "used"
                pool_row["used_at"] = pool_row.get("used_at") or now
                pool_row["completed_at"] = pool_row.get("completed_at") or now
                pool_row["note"] = pool_row.get("note") or "导入为已注册账号，用于 Codex 授权"
                pool_row["copy_line"] = _generic_api_email_line(pool_row)
                original_line = _generic_api_email_line(pool_row)
            else:
                password = (raw.get("password") or "").strip()
                client_id = (raw.get("client_id") or raw.get("clientId") or "").strip()
                refresh_token = (raw.get("refresh_token") or raw.get("refreshToken") or "").strip()
                if not (password and client_id and refresh_token):
                    skipped += 1
                    continue
                pool_row = _find_by_email(outlook_rows, email)
                if pool_row is None:
                    pool_row = {
                        "id": _next_id(outlook_rows),
                        "email": email,
                        "password": password,
                        "client_id": client_id,
                        "refresh_token": refresh_token,
                        "status": "used",
                        "used_at": now,
                        "note": "导入为已注册账号，用于 Codex 授权",
                        "imported_at": now,
                    }
                    outlook_rows.append(pool_row)
                else:
                    pool_row["password"] = password or pool_row.get("password")
                    pool_row["client_id"] = client_id or pool_row.get("client_id")
                    pool_row["refresh_token"] = refresh_token or pool_row.get("refresh_token")
                pool_row["status"] = "used"
                pool_row["used_at"] = pool_row.get("used_at") or now
                pool_row["completed_at"] = pool_row.get("completed_at") or now
                pool_row["note"] = pool_row.get("note") or "导入为已注册账号，用于 Codex 授权"
                pool_row["copy_line"] = _outlook_line(pool_row)
                original_line = _outlook_line(pool_row)

            row_id = _next_id(accounts)
            access_token = (raw.get("access_token") or raw.get("token") or "").strip()
            totp_secret = (raw.get("totp_secret") or raw.get("totp") or "").strip() or None
            account = {
                "id": row_id,
                "email": email,
                "created_at": now,
                "access_token": access_token,
                "totp_secret": totp_secret,
                "user_id": raw.get("user_id"),
                "user_name": raw.get("user_name") or "Imported Account",
                "plan_type": raw.get("plan_type"),
                "expires_at": raw.get("expires_at"),
                "device_id": raw.get("device_id"),
                "proxy_used": raw.get("proxy_used"),
                "email_source": source,
                "extra_json": json.dumps({"imported_registered": True}, ensure_ascii=False),
                "codex_status": raw.get("codex_status") or "",
                "codex_error": raw.get("codex_error"),
                "updated_at": now,
                "original_email_line": original_line,
            }
            if source == "outlook":
                account["password"] = pool_row.get("password")
                account["client_id"] = pool_row.get("client_id")
                account["refresh_token"] = pool_row.get("refresh_token")
            account["copy_line"] = _account_line(account)
            accounts.append(account)

            pool_row["registered_account_id"] = row_id
            pool_row["access_token"] = access_token
            if totp_secret:
                pool_row["totp_secret"] = totp_secret
            inserted += 1

        _save_outlook(outlook_rows)
        _save_generic_api_emails(generic_rows)
        _save_accounts(accounts)
        return inserted, skipped


def claim_next_outlook() -> dict | None:
    """原子领取一个可用 Outlook 账号并标记为 used。"""
    with _LOCK:
        rows = sorted(_load_outlook(), key=lambda x: int(x.get("id") or 0))
        row = next((r for r in rows if r.get("status") == "available"), None)
        if row is None:
            return None
        row["status"] = "used"
        row["used_at"] = _now()
        row["note"] = None
        _save_outlook(rows)
        return _decorate_outlook(row)


def release_outlook(email: str, status: str = "available", note: str | None = None) -> None:
    """把账号状态改回 available，或标记为 used/failed/disabled。"""
    with _LOCK:
        rows = _load_outlook()
        row = _find_by_email(rows, email)
        if row is None:
            return
        row["status"] = status
        if status == "available":
            row["used_at"] = None
        elif status in ("used", "failed", "disabled"):
            row["used_at"] = row.get("used_at") or _now()
        if note is not None:
            row["note"] = note
        _save_outlook(rows)


def release_unconsumed_outlook(email: str, note: str | None = None) -> bool:
    """原子回收未生成本地账号且仍为 used 的 Outlook 邮箱。"""
    with _LOCK:
        if _find_by_email(_load_accounts(), email) is not None:
            return False
        rows = _load_outlook()
        row = _find_by_email(rows, email)
        if row is None or row.get("status") != "used":
            return False
        row["status"] = "available"
        row["used_at"] = None
        if note is not None:
            row["note"] = note
        _save_outlook(rows)
        return True


def delete_outlook(email: str) -> bool:
    """从邮箱池彻底删除一个邮箱（按 email 匹配）。返回是否删到。"""
    with _LOCK:
        rows = _load_outlook()
        target = (email or "").lower()
        new_rows = [r for r in rows if (r.get("email") or "").lower() != target]
        if len(new_rows) == len(rows):
            return False
        _save_outlook(new_rows)
        return True


def list_outlook_pool(status: str | None = None, limit: int = 500) -> list[dict]:
    with _LOCK:
        account_by_email = {
            (a.get("email") or "").lower(): a
            for a in _load_accounts()
        }
        rows = _load_outlook()
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows = sorted(rows, key=lambda x: int(x.get("id") or 0), reverse=True)
        return [_decorate_outlook(r, account_by_email) for r in rows[:limit]]


def outlook_pool_summary() -> dict:
    with _LOCK:
        out = {"available": 0, "used": 0, "failed": 0}
        for row in _load_outlook():
            status = row.get("status") or "available"
            out[status] = out.get(status, 0) + 1
        out["total"] = sum(v for k, v in out.items() if k != "total")
        return out


def get_outlook_by_email(email: str) -> dict | None:
    with _LOCK:
        row = _find_by_email(_load_outlook(), email)
        return _decorate_outlook(row) if row else None


# ============================================================
# generic_api email pool
# ============================================================

def import_generic_api_emails(records: list[dict]) -> tuple[int, int]:
    """
    批量导入通用 API 取码邮箱。
    records 元素：{email, code_url}
    返回 (新增数, 跳过数)。
    """
    with _LOCK:
        rows = _load_generic_api_emails()
        inserted = skipped = 0
        for raw in records:
            email = (raw.get("email") or "").strip()
            code_url = (raw.get("code_url") or raw.get("url") or "").strip()
            if not email or not code_url:
                skipped += 1
                continue
            if _find_by_email(rows, email):
                skipped += 1
                continue
            row = {
                "id": _next_id(rows),
                "email": email,
                "code_url": code_url,
                "status": "available",
                "used_at": None,
                "note": None,
                "imported_at": _now(),
            }
            row["copy_line"] = _generic_api_email_line(row)
            rows.append(row)
            inserted += 1
        _save_generic_api_emails(rows)
        return inserted, skipped


def claim_next_generic_api_email() -> dict | None:
    """原子领取一个可用通用 API 邮箱并标记为 used。"""
    with _LOCK:
        rows = sorted(_load_generic_api_emails(), key=lambda x: int(x.get("id") or 0))
        row = next((r for r in rows if r.get("status") == "available"), None)
        if row is None:
            return None
        row["status"] = "used"
        row["used_at"] = _now()
        row["note"] = None
        _save_generic_api_emails(rows)
        return _decorate_generic_api_email(row)


def release_generic_api_email(email: str, status: str = "available", note: str | None = None) -> None:
    """把通用 API 邮箱状态改回 available，或标记为 failed/used。"""
    with _LOCK:
        rows = _load_generic_api_emails()
        row = _find_by_email(rows, email)
        if row is None:
            return
        row["status"] = status
        if status == "available":
            row["used_at"] = None
        elif status in ("used", "failed", "disabled"):
            row["used_at"] = row.get("used_at") or _now()
        if note is not None:
            row["note"] = note
        _save_generic_api_emails(rows)


def release_unconsumed_generic_api_email(email: str, note: str | None = None) -> bool:
    """原子回收未生成本地账号且仍为 used 的通用 API 邮箱。"""
    with _LOCK:
        if _find_by_email(_load_accounts(), email) is not None:
            return False
        rows = _load_generic_api_emails()
        row = _find_by_email(rows, email)
        if row is None or row.get("status") != "used":
            return False
        row["status"] = "available"
        row["used_at"] = None
        if note is not None:
            row["note"] = note
        _save_generic_api_emails(rows)
        return True


def delete_generic_api_email(email: str) -> bool:
    """从通用 API 邮箱池彻底删除一个邮箱。"""
    with _LOCK:
        rows = _load_generic_api_emails()
        target = (email or "").lower()
        new_rows = [r for r in rows if (r.get("email") or "").lower() != target]
        if len(new_rows) == len(rows):
            return False
        _save_generic_api_emails(new_rows)
        return True


def list_generic_api_email_pool(status: str | None = None, limit: int = 500) -> list[dict]:
    with _LOCK:
        account_by_email = {
            (a.get("email") or "").lower(): a
            for a in _load_accounts()
        }
        rows = _load_generic_api_emails()
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows = sorted(rows, key=lambda x: int(x.get("id") or 0), reverse=True)
        return [_decorate_generic_api_email(r, account_by_email) for r in rows[:limit]]


def generic_api_email_pool_summary() -> dict:
    with _LOCK:
        out = {"available": 0, "used": 0, "failed": 0}
        for row in _load_generic_api_emails():
            status = row.get("status") or "available"
            out[status] = out.get(status, 0) + 1
        out["total"] = sum(v for k, v in out.items() if k != "total")
        return out


def get_generic_api_email_by_email(email: str) -> dict | None:
    with _LOCK:
        row = _find_by_email(_load_generic_api_emails(), email)
        return _decorate_generic_api_email(row) if row else None


# ============================================================
# Codex 授权账号（来自 codex_accounts/codex-邮箱-plan.json）
# ============================================================

def _sync_codex_credentials_collection() -> dict:
    """Keep CPA-compatible credential files mirrored in PostgreSQL."""
    local_records: dict[str, dict] = {}
    if _CODEX_DIR.exists():
        for path in _CODEX_DIR.glob("codex-*.json"):
            try:
                local_records[path.name] = {
                    "content": json.loads(path.read_text(encoding="utf-8")),
                    "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                }
            except Exception:
                continue
    found, stored = postgres_store.load_collection(_CODEX_CREDENTIALS_COLLECTION)
    records = stored if found and isinstance(stored, dict) else {}
    changed = False
    for filename, record in local_records.items():
        if records.get(filename) != record:
            records[filename] = record
            changed = True
    if changed or not found:
        postgres_store.save_collection(_CODEX_CREDENTIALS_COLLECTION, records)
    return records


def save_codex_credential_record(filename: str, content: dict) -> None:
    """Mirror a newly written CPA-compatible credential into PostgreSQL."""
    records = _sync_codex_credentials_collection()
    records[filename] = {"content": content, "mtime": _now()}
    postgres_store.save_collection(_CODEX_CREDENTIALS_COLLECTION, records)


def write_codex_credential(filename: str, content: dict) -> None:
    """安全覆盖一份现有 Codex 凭证，并同步 PostgreSQL 镜像。"""
    with _LOCK:
        if not filename.startswith("codex-") or not filename.endswith(".json"):
            raise ValueError(f"非法文件名: {filename}")
        if "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError(f"非法文件名: {filename}")
        if not isinstance(content, dict):
            raise ValueError("Codex 凭证必须是 JSON 对象")
        path = _CODEX_DIR / filename
        if not path.exists() or not path.is_file():
            raise ValueError(f"文件不存在: {filename}")
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        save_codex_credential_record(filename, content)

def _load_codex_export_state() -> dict:
    """读导出状态映射 {filename: {exported_at, exported_count}}。不存在返回 {}。"""
    data = _read_json(_CODEX_EXPORT_STATE, {})
    return data if isinstance(data, dict) else {}


def _save_codex_export_state(state: dict) -> None:
    _write_json(_CODEX_EXPORT_STATE, state)


def list_codex_accounts(archived: str | bool | None = "0", date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """
    扫 codex_accounts/ 目录，每个 codex-*.json 是一条 CPA 兼容凭证。
    返回带元信息的列表（含导出状态、文件大小、token 预览等）。
    archived: '0'=仅未归档（默认）/ 'only'=仅归档 / 'all'=全部；
    date_from/date_to 按文件修改时间（mtime）筛选（ISO 或 YYYY-MM-DD）。
    """
    from core.codex_token_refresh_service import oauth_metadata, refresh_error_requires_reauth

    with _LOCK:
        out = []
        _sync_codex_credentials_collection()
        if not _CODEX_DIR.exists():
            return out
        export_state = _load_codex_export_state()
        d_from = _parse_iso_dt(date_from)
        d_to = _parse_iso_dt(date_to, end_of_day=True)
        for path in sorted(_CODEX_DIR.glob("codex-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                content = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            fname = path.name
            es = export_state.get(fname) or {}
            rec_archived = bool(es.get("archived"))
            if archived in (True, "1", "true", "yes", "only"):
                if not rec_archived:
                    continue
            elif archived in ("all", "include"):
                pass
            else:
                if rec_archived:
                    continue
            mtime_dt = datetime.fromtimestamp(path.stat().st_mtime)
            if d_from and mtime_dt < d_from:
                continue
            if d_to and mtime_dt > d_to:
                continue
            # 从文件名抽 email 和 plan：codex-{email}.json 或 codex-{email}-{plan}.json
            stem = path.stem  # codex-邮箱-plan
            without_prefix = stem[len("codex-"):] if stem.startswith("codex-") else stem
            # plan 可能为空。简单做法：直接读 JSON 里的 email（更准），文件名只做 fallback
            email = content.get("email") or ""
            if not email:
                # JSON 里 email 为空（旧 bug 产物），从文件名兜底
                # 文件名格式 codex-{email}-{plan}.json，email 里可能有 - 但是常见邮箱不会有
                # 简单做法：去掉末尾 -plan（如 -free / -plus / -team），剩下的当 email
                parts = without_prefix.rsplit("-", 1)
                if len(parts) == 2 and parts[1].lower() in ("free", "plus", "team", "pro", "enterprise"):
                    email = parts[0]
                else:
                    email = without_prefix
            # 推断 plan
            plan = ""
            if "-" in without_prefix:
                tail = without_prefix.rsplit("-", 1)[-1].lower()
                if tail in ("free", "plus", "team", "pro", "enterprise"):
                    plan = tail
            oauth = oauth_metadata(content)
            oauth["oauth_reauth_required"] = refresh_error_requires_reauth(es.get("oauth_refresh_error"))
            out.append({
                "filename": fname,
                "path": str(path),
                "email": email,
                "plan": plan,
                "account_id": content.get("account_id", ""),
                "type": content.get("type", "codex"),
                "last_refresh": content.get("last_refresh", ""),
                "expired": content.get("expired", ""),
                "access_token_preview": (content.get("access_token", "") or "")[:32],
                "size": path.stat().st_size,
                "mtime": mtime_dt.isoformat(timespec="seconds"),
                "exported_at": es.get("exported_at"),
                "exported_count": es.get("exported_count", 0),
                "sub2_uploaded_at": es.get("sub2_uploaded_at"),
                "sub2_uploaded_count": es.get("sub2_uploaded_count", 0),
                "sub2_sync_error": es.get("sub2_sync_error"),
                "oauth_refresh_attempted_at": es.get("oauth_refresh_attempted_at"),
                "oauth_refresh_error": es.get("oauth_refresh_error"),
                "archived": rec_archived,
                "archived_at": es.get("archived_at"),
                **oauth,
            })
        return out


def archive_codex(filename: str, archived: bool = True) -> dict | None:
    """归档/取消归档一条 Codex 授权凭证（状态记录在导出状态文件）。不存在返回 None。"""
    with _LOCK:
        if not filename.startswith("codex-") or not filename.endswith(".json"):
            raise ValueError(f"非法文件名: {filename}")
        if "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError(f"非法文件名: {filename}")
        path = _CODEX_DIR / filename
        if not path.exists() or not path.is_file():
            return None
        state = _load_codex_export_state()
        rec = state.get(filename) or {}
        rec["archived"] = bool(archived)
        rec["archived_at"] = _now() if archived else None
        state[filename] = rec
        _save_codex_export_state(state)
        return rec


def read_codex_credential(filename: str) -> tuple[str, str]:
    """
    读取一个 codex-*.json 文件原始内容。
    Returns: (content_string, filename)
    抛 ValueError：文件名不合法（防目录穿越）/ 不存在。
    """
    with _LOCK:
        # 防注入：只允许 codex-*.json 模式，不允许路径分隔符
        if not filename.startswith("codex-") or not filename.endswith(".json"):
            raise ValueError(f"非法文件名: {filename}")
        if "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError(f"非法文件名: {filename}")
        path = _CODEX_DIR / filename
        records = _sync_codex_credentials_collection()
        record = records.get(filename) or {}
        content = record.get("content")
        if isinstance(content, dict):
            return json.dumps(content, ensure_ascii=False, indent=2) + "\n", filename
        if not path.exists() or not path.is_file():
            raise ValueError(f"文件不存在: {filename}")
        return path.read_text(encoding="utf-8"), filename


def mark_codex_exported(filename: str) -> dict:
    """
    标记某个 codex 凭证已导出（导出计数 +1，记录最近导出时间）。
    Returns: 该 filename 当前的导出状态记录。
    """
    with _LOCK:
        state = _load_codex_export_state()
        rec = state.get(filename) or {"exported_count": 0}
        rec["exported_count"] = int(rec.get("exported_count", 0)) + 1
        rec["exported_at"] = _now()
        state[filename] = rec
        _save_codex_export_state(state)
        return rec


def mark_codex_sub2_uploaded(filename: str) -> dict:
    """记录凭证曾成功上传 sub2api，供后续 token 刷新后定向同步。"""
    with _LOCK:
        state = _load_codex_export_state()
        rec = state.get(filename) or {}
        rec["sub2_uploaded_count"] = int(rec.get("sub2_uploaded_count", 0)) + 1
        rec["sub2_uploaded_at"] = _now()
        rec["sub2_sync_error"] = None
        state[filename] = rec
        _save_codex_export_state(state)
        return rec


def mark_codex_sub2_sync_error(filename: str, error: str | None) -> dict:
    with _LOCK:
        state = _load_codex_export_state()
        rec = state.get(filename) or {}
        rec["sub2_sync_error"] = str(error or "")[:500] or None
        state[filename] = rec
        _save_codex_export_state(state)
        return rec


def mark_codex_oauth_refresh(filename: str, *, error: str | None = None) -> dict:
    """保存刷新尝试时间和脱敏错误；token 本身只保存在凭证文件中。"""
    with _LOCK:
        state = _load_codex_export_state()
        rec = state.get(filename) or {}
        rec["oauth_refresh_attempted_at"] = _now()
        rec["oauth_refresh_error"] = str(error or "")[:500] or None
        state[filename] = rec
        _save_codex_export_state(state)
        return rec


def reset_codex_exported(filename: str) -> None:
    """只清掉导出计数，保留归档、OAuth 刷新和 sub2 同步元数据。"""
    with _LOCK:
        state = _load_codex_export_state()
        if filename in state:
            rec = state.get(filename) or {}
            rec.pop("exported_at", None)
            rec.pop("exported_count", None)
            if rec:
                state[filename] = rec
            else:
                del state[filename]
            _save_codex_export_state(state)


def delete_codex_credential(filename: str) -> bool:
    """删除一个本地 codex-*.json 凭证文件，并清理导出状态。"""
    with _LOCK:
        if not filename.startswith("codex-") or not filename.endswith(".json"):
            raise ValueError(f"非法文件名: {filename}")
        if "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError(f"非法文件名: {filename}")
        path = _CODEX_DIR / filename
        if not path.exists() or not path.is_file():
            return False
        path.unlink()
        records = _sync_codex_credentials_collection()
        if filename in records:
            del records[filename]
            postgres_store.save_collection(_CODEX_CREDENTIALS_COLLECTION, records)
        state = _load_codex_export_state()
        if filename in state:
            del state[filename]
            _save_codex_export_state(state)
        return True


def codex_accounts_summary() -> dict:
    """codex 账号汇总：总数 / 已导出 / 未导出。"""
    with _LOCK:
        rows = list_codex_accounts()
        total = len(rows)
        exported = sum(1 for r in rows if r.get("exported_count", 0) > 0)
        return {
            "total": total,
            "exported": exported,
            "pending": total - exported,
        }


# ============================================================
# registration_jobs
# ============================================================

def _new_job_row(
    rows: list[dict],
    *,
    email_source: str,
    job_type: str = "registration",
    parent_job_id: int | None = None,
    root_job_id: int | None = None,
    retry_attempt: int = 0,
    retry_action: str | None = None,
    email: str | None = None,
    account_id: int | None = None,
    batch_id: str | None = None,
    batch_index: int | None = None,
    batch_size: int | None = None,
    batch_workers: int | None = None,
) -> dict:
    job_uuid = str(uuid.uuid4())
    log_file = str(_LOG_DIR / f"{job_uuid}.log")
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    return {
        "id": _next_id(rows),
        "job_uuid": job_uuid,
        "job_type": job_type,
        "parent_job_id": parent_job_id,
        "root_job_id": root_job_id,
        "retry_attempt": int(retry_attempt or 0),
        "retry_action": retry_action,
        "email_source": email_source,
        "batch_id": str(batch_id or job_uuid),
        "batch_index": int(batch_index or 1),
        "batch_size": int(batch_size or 1),
        "batch_workers": int(batch_workers or 1),
        "email": email,
        "status": "pending",
        "error_message": None,
        "log_file": log_file,
        "started_at": None,
        "completed_at": None,
        "account_id": account_id,
        "progress_stage": None,
        "progress_updated_at": None,
        "progress_steps": {},
        "proxy_provider": None,
        "proxy_status": None,
        "proxy_endpoint": None,
        "proxy_exit_ip": None,
        "proxy_region": None,
        "proxy_acquired_at": None,
        "proxy_expires_at": None,
        "created_at": _now(),
    }


def create_job(
    email_source: str,
    *,
    batch_id: str | None = None,
    batch_index: int | None = None,
    batch_size: int | None = None,
    batch_workers: int | None = None,
) -> dict:
    """创建一个首次执行的 pending 注册任务。"""
    with _LOCK:
        rows = _load_jobs()
        row = _new_job_row(
            rows,
            email_source=email_source,
            batch_id=batch_id,
            batch_index=batch_index,
            batch_size=batch_size,
            batch_workers=batch_workers,
        )
        rows.append(row)
        _save_jobs(rows)
        return dict(row)


def create_retry_job(
    source_job_id: int,
    *,
    job_type: str,
    email_source: str,
    email: str | None = None,
    account_id: int | None = None,
) -> tuple[dict, bool]:
    """原子创建重试子任务；同一任务链已有活跃任务时直接复用。"""
    with _LOCK:
        rows = _load_jobs()
        source = next((r for r in rows if int(r.get("id") or 0) == int(source_job_id)), None)
        if source is None:
            raise LookupError("任务不存在")
        if source.get("status") not in ("failed", "stopped", "cancelled"):
            raise ValueError(f"当前状态不支持重试：{source.get('status')}")

        root_id = int(source.get("root_job_id") or source.get("id"))
        active_states = {"pending", "running", "stopping"}
        active = next((
            r for r in rows
            if int(r.get("id") or 0) != int(source_job_id)
            and int(r.get("root_job_id") or 0) == root_id
            and r.get("status") in active_states
        ), None)
        if active is not None:
            if active.get("job_type", "registration") != job_type:
                raise ValueError(f"已有其他类型重试任务 #{active.get('id')} 在排队或运行中")
            return dict(active), False

        attempts = [
            int(r.get("retry_attempt") or 0)
            for r in rows
            if int(r.get("id") or 0) == root_id or int(r.get("root_job_id") or 0) == root_id
        ]
        row = _new_job_row(
            rows,
            email_source=email_source,
            job_type=job_type,
            parent_job_id=int(source_job_id),
            root_job_id=root_id,
            retry_attempt=(max(attempts) if attempts else 0) + 1,
            retry_action=("codex" if job_type == "codex_retry" else "registration"),
            email=email,
            account_id=account_id,
        )
        rows.append(row)
        _save_jobs(rows)
        return dict(row), True


def update_job(
    job_id: int,
    *,
    status: str | None = None,
    email: str | None = None,
    error: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    account_id: int | None = None,
    proxy_provider: str | None = None,
    proxy_status: str | None = None,
    proxy_endpoint: str | None = None,
    proxy_exit_ip: str | None = None,
    proxy_region: str | None = None,
    proxy_acquired_at: str | None = None,
    proxy_expires_at: str | None = None,
) -> None:
    with _LOCK:
        rows = _load_jobs()
        row = next((r for r in rows if int(r.get("id") or 0) == int(job_id)), None)
        if row is None:
            return
        if status is not None:
            row["status"] = status
        if email is not None:
            row["email"] = email
        if error is not None:
            row["error_message"] = error
        if started_at is not None:
            row["started_at"] = started_at
        if completed_at is not None:
            row["completed_at"] = completed_at
        if account_id is not None:
            row["account_id"] = account_id
        if proxy_provider is not None:
            row["proxy_provider"] = proxy_provider
        if proxy_status is not None:
            row["proxy_status"] = proxy_status
        if proxy_endpoint is not None:
            row["proxy_endpoint"] = proxy_endpoint
        if proxy_exit_ip is not None:
            row["proxy_exit_ip"] = proxy_exit_ip
        if proxy_region is not None:
            row["proxy_region"] = proxy_region
        if proxy_acquired_at is not None:
            row["proxy_acquired_at"] = proxy_acquired_at
        if proxy_expires_at is not None:
            row["proxy_expires_at"] = proxy_expires_at
        _save_jobs(rows)


def update_job_progress(
    job_id: int,
    stage: str,
    state: str = "running",
    detail: str | None = None,
) -> None:
    """原子更新注册阶段；进入新阶段时自动结束仍在运行的前置阶段。"""
    stage = str(stage or "").strip()
    state = str(state or "running").strip().lower()
    if stage not in _JOB_PROGRESS_KEYS:
        raise ValueError(f"未知任务阶段: {stage}")
    if state not in _JOB_PROGRESS_STATES:
        raise ValueError(f"未知阶段状态: {state}")

    with _LOCK:
        rows = _load_jobs()
        row = next((r for r in rows if int(r.get("id") or 0) == int(job_id)), None)
        if row is None:
            return
        now = _now()
        steps = row.get("progress_steps")
        if not isinstance(steps, dict):
            steps = {}

        current_index = _JOB_PROGRESS_KEYS.index(stage)
        if state == "running":
            for prior_key in _JOB_PROGRESS_KEYS[:current_index]:
                prior = steps.get(prior_key)
                if isinstance(prior, dict) and prior.get("state") == "running":
                    prior["state"] = "success"
                    prior["completed_at"] = now

        item = steps.get(stage)
        if not isinstance(item, dict):
            item = {}
        if state == "running" and not item.get("started_at"):
            item["started_at"] = now
        elif state in {"success", "failed", "skipped", "stopped"}:
            item["started_at"] = item.get("started_at") or now
            item["completed_at"] = now
        item["state"] = state
        if detail is not None:
            item["detail"] = str(detail)[:300]
        steps[stage] = item
        row["progress_steps"] = steps
        row["progress_stage"] = stage
        row["progress_updated_at"] = now
        _save_jobs(rows)


def finish_job_progress(
    job_id: int,
    *,
    success: bool,
    detail: str | None = None,
    failure_state: str = "failed",
) -> None:
    """收口任务进度：保留具体失败节点，并用“完成”节点展示任务总耗时。"""
    with _LOCK:
        rows = _load_jobs()
        row = next((r for r in rows if int(r.get("id") or 0) == int(job_id)), None)
        if row is None:
            return
        now = _now()
        steps = row.get("progress_steps")
        if not isinstance(steps, dict):
            steps = {}
        current = str(row.get("progress_stage") or "email")
        if current not in _JOB_PROGRESS_KEYS:
            current = "email"

        overall_started_at = row.get("started_at") or row.get("created_at") or now
        work_stage_keys = tuple(key for key in _JOB_PROGRESS_KEYS if key != "complete")

        if success:
            for key in work_stage_keys:
                item = steps.get(key)
                if not isinstance(item, dict):
                    item = {"started_at": now}
                # 已由具体流程上报的终态不能被任务级 success 覆盖；例如账号
                # 注册成功但 Codex 授权失败时，仍应保留失败节点供 UI 提示。
                if item.get("state") not in {"skipped", "success", "failed", "stopped"}:
                    item["state"] = "success"
                item["completed_at"] = item.get("completed_at") or now
                steps[key] = item
        else:
            terminal_state = "stopped" if failure_state == "stopped" else "failed"
            # 套餐查询可能在 Codex 失败后继续成功。此时当前节点已经是 plan_check，
            # 不能把它误改成失败；优先保留流程中真正失败/停止的节点。
            failed_key = next((
                key for key in work_stage_keys
                if isinstance(steps.get(key), dict)
                and steps[key].get("state") in {"failed", "stopped"}
            ), None)
            target_key = failed_key or (current if current != "complete" else "email")
            item = steps.get(target_key)
            if not isinstance(item, dict):
                item = {"started_at": now}
            if item.get("state") not in {"failed", "stopped"}:
                item["state"] = terminal_state
            item["completed_at"] = now
            if detail is not None and not item.get("detail"):
                item["detail"] = str(detail)[:300]
            steps[target_key] = item

        complete_state = "success" if success else ("stopped" if failure_state == "stopped" else "failed")
        complete_item = steps.get("complete")
        if not isinstance(complete_item, dict):
            complete_item = {}
        complete_item.update({
            "state": complete_state,
            "started_at": overall_started_at,
            "completed_at": now,
            "detail": (
                "任务已完成"
                if success
                else str(detail or ("任务已停止" if complete_state == "stopped" else "任务失败"))[:300]
            ),
        })
        steps["complete"] = complete_item
        row["progress_stage"] = "complete"
        row["progress_steps"] = steps
        row["progress_updated_at"] = now
        _save_jobs(rows)


def recover_interrupted_registration_jobs() -> int:
    """启动时把上个进程遗留的排队/运行任务收口为可重试失败状态。"""
    with _LOCK:
        rows = _load_jobs()
        accounts = _load_accounts()
        now = _now()
        recovered = 0
        account_changed = False
        for row in rows:
            if str(row.get("status") or "") not in {"pending", "running", "stopping"}:
                continue
            detail = "WebUI 进程重启导致任务中断；浏览器和接码资源将在启动恢复阶段回收，请重新执行任务"
            row["status"] = "failed"
            row["error_message"] = detail
            row["completed_at"] = now
            if row.get("proxy_status") in {"acquiring", "leased"}:
                row["proxy_status"] = "interrupted"

            steps = row.get("progress_steps")
            if not isinstance(steps, dict):
                steps = {}
            current = str(row.get("progress_stage") or "email")
            if current not in _JOB_PROGRESS_KEYS:
                current = "email"
            item = steps.get(current)
            if not isinstance(item, dict):
                item = {"started_at": row.get("started_at") or now}
            item.update({"state": "failed", "detail": detail[:300], "completed_at": now})
            steps[current] = item
            row["progress_steps"] = steps
            row["progress_stage"] = current
            row["progress_updated_at"] = now

            if str(row.get("job_type") or "") == "codex_retry":
                email = str(row.get("email") or "").strip().lower()
                account = next(
                    (item for item in accounts if str(item.get("email") or "").strip().lower() == email),
                    None,
                )
                if account is not None and str(account.get("codex_status") or "") == "retrying":
                    account["codex_status"] = "failed"
                    account["codex_error"] = "WebUI 进程重启导致 Codex OAuth 中断，请重新补跑"
                    account["updated_at"] = now
                    account_changed = True
            recovered += 1

        if recovered:
            _save_jobs(rows)
        if account_changed:
            _save_accounts(accounts)
        return recovered


def list_jobs(limit: int = 100) -> list[dict]:
    with _LOCK:
        rows = sorted(_load_jobs(), key=lambda x: int(x.get("id") or 0), reverse=True)
        return [dict(r) for r in rows[:limit]]


def get_job(job_id: int) -> dict | None:
    with _LOCK:
        row = next((r for r in _load_jobs() if int(r.get("id") or 0) == int(job_id)), None)
        return dict(row) if row else None


def get_successful_retry_for_job(job_id: int) -> dict | None:
    """返回同一任务链中已成功的其他重试任务，用于保留原任务历史状态并阻止重复重试。"""
    with _LOCK:
        rows = _load_jobs()
        source = next((r for r in rows if int(r.get("id") or 0) == int(job_id)), None)
        if source is None:
            return None
        root_id = int(source.get("root_job_id") or source.get("id") or 0)
        matches = [
            r for r in rows
            if int(r.get("id") or 0) != int(job_id)
            and int(r.get("root_job_id") or 0) == root_id
            and r.get("status") == "success"
        ]
        if not matches:
            return None
        return dict(max(matches, key=lambda r: int(r.get("id") or 0)))


def delete_job(job_id: int, *, delete_log: bool = True, allow_running: bool = False) -> bool:
    """
    删除一个注册任务记录；默认同时删除该任务日志文件。返回是否删除到记录。
    默认不删除 running 任务，避免后台线程仍在执行但前端记录消失。
    """
    with _LOCK:
        rows = _load_jobs()
        idx = next((i for i, r in enumerate(rows) if int(r.get("id") or 0) == int(job_id)), None)
        if idx is None:
            return False
        if not allow_running and rows[idx].get("status") in ("running", "stopping"):
            return False
        row = rows.pop(idx)
        _save_jobs(rows)

    if delete_log:
        log_file = row.get("log_file")
        if log_file:
            try:
                Path(log_file).unlink(missing_ok=True)
            except Exception:
                pass
    return True


# ============================================================
# 迁移与路径
# ============================================================


def migrate_legacy_files() -> dict:
    """
    把历史 accounts/*.json、outlook_accounts.txt、outlook_accounts_used.json
    迁移到当前 PostgreSQL 主存储及兼容导出文件。多次调用是幂等的。
    """
    summary = {
        "accounts_imported": 0,
        "outlook_imported": 0,
        "outlook_skipped": 0,
    }
    accounts_dir = _PROJECT_ROOT / "accounts"
    if accounts_dir.exists():
        for jf in accounts_dir.glob("*.json"):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if not data.get("email") or not data.get("access_token"):
                    continue
                extra = data.get("extra") or {}
                user = extra.get("user") or {}
                account = extra.get("account") or {}
                insert_account(
                    email=data["email"],
                    access_token=data["access_token"],
                    totp_secret=data.get("totp_secret"),
                    user_id=user.get("id"),
                    user_name=user.get("name"),
                    plan_type=account.get("planType"),
                    expires_at=extra.get("expires"),
                    device_id=extra.get("device_id"),
                    extra=extra,
                )
                summary["accounts_imported"] += 1
            except Exception:
                continue

    for txt in (_PROJECT_ROOT / "outlook_accounts.txt", _OUTLOOK_TXT):
        if txt.exists():
            records = []
            for line in txt.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("----")
                # 支持 4 段或 6 段格式
                if len(parts) == 4:
                    email, password, client_id, refresh_token = (p.strip() for p in parts)
                elif len(parts) == 6:
                    email, password, client_id, refresh_token, _, _ = (p.strip() for p in parts)
                else:
                    continue
                records.append({
                    "email": email,
                    "password": password,
                    "client_id": client_id,
                    "refresh_token": refresh_token,
                })
            ins, skip = import_outlook_accounts(records)
            summary["outlook_imported"] += ins
            summary["outlook_skipped"] += skip

    used = _PROJECT_ROOT / "outlook_accounts_used.json"
    if used.exists():
        try:
            emails = json.loads(used.read_text(encoding="utf-8"))
            for email in emails:
                release_outlook(email, status="used")
        except Exception:
            pass

    return summary


def db_path() -> Path:
    """兼容旧名称，返回当前文件存储目录。"""
    return _DATA_DIR


def storage_paths() -> dict:
    return {
        "outlook_json": str(_OUTLOOK_JSON),
        "outlook_txt": str(_OUTLOOK_TXT),
        "accounts_json": str(_ACCOUNTS_JSON),
        "accounts_txt": str(_ACCOUNTS_TXT),
        "tokens_txt": str(_TOKENS_TXT),
        "viewer_html": str(_VIEWER_HTML),
        "jobs_json": str(_JOBS_JSON),
        "logs_dir": str(_LOG_DIR),
    }


def refresh_static_viewer() -> Path:
    """手动刷新静态查看器，返回 HTML 路径。"""
    with _LOCK:
        outlook_rows = _load_outlook()
        account_rows = _load_accounts()
        _sync_outlook_txt(outlook_rows)
        _sync_accounts_txt(account_rows)
        _sync_tokens_txt(account_rows)
        return _render_static_viewer(outlook_rows=outlook_rows, account_rows=account_rows)


# ============================================================
# Domain email pool（Cloudflare 域名邮箱跟踪）
# ============================================================

_DOMAIN_EMAIL_JSON = _PROJECT_ROOT / "用于注册的域名邮箱.json"


def _load_domain_pool() -> list[dict]:
    rows = _read_json(_DOMAIN_EMAIL_JSON, [])
    return rows if isinstance(rows, list) else []


def _save_domain_pool(rows: list[dict]) -> None:
    _write_json(_DOMAIN_EMAIL_JSON, rows)


def _find_domain_email(rows: list[dict], email: str) -> dict | None:
    target = (email or "").lower()
    return next((r for r in rows if (r.get("email") or "").lower() == target), None)


def claim_next_domain_email(email: str) -> dict:
    """记录一个新的域名邮箱地址到池中（标记为 available）。"""
    with _LOCK:
        rows = _load_domain_pool()
        if _find_domain_email(rows, email):
            # 已存在，直接返回
            row = _find_domain_email(rows, email)
            return row
        row = {
            "id": _next_id(rows),
            "email": email,
            "status": "available",
            "used_at": None,
            "note": None,
            "created_at": _now(),
        }
        rows.append(row)
        _save_domain_pool(rows)
        return dict(row)


def release_domain_email(email: str, status: str = "available", note: str | None = None) -> None:
    """更新域名邮箱状态。"""
    with _LOCK:
        rows = _load_domain_pool()
        row = _find_domain_email(rows, email)
        if row is None:
            return
        row["status"] = status
        if status == "available":
            row["used_at"] = None
        elif status in ("used", "failed", "disabled"):
            row["used_at"] = row.get("used_at") or _now()
        if note is not None:
            row["note"] = note
        _save_domain_pool(rows)


def release_unconsumed_domain_email(email: str, note: str | None = None) -> bool:
    """原子回收未生成本地账号且仍为 used 的域名邮箱。"""
    with _LOCK:
        if _find_by_email(_load_accounts(), email) is not None:
            return False
        rows = _load_domain_pool()
        row = _find_domain_email(rows, email)
        if row is None or row.get("status") != "used":
            return False
        row["status"] = "available"
        row["used_at"] = None
        if note is not None:
            row["note"] = note
        _save_domain_pool(rows)
        return True


def get_domain_email_by_email(email: str) -> dict | None:
    with _LOCK:
        row = _find_domain_email(_load_domain_pool(), email)
        return dict(row) if row else None


def list_domain_email_pool(status: str | None = None, limit: int = 500) -> list[dict]:
    with _LOCK:
        rows = sorted(_load_domain_pool(), key=lambda x: int(x.get("id") or 0), reverse=True)
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return [dict(r) for r in rows[:limit]]


def domain_email_pool_summary() -> dict:
    with _LOCK:
        out: dict[str, int] = {"available": 0, "used": 0, "failed": 0}
        for row in _load_domain_pool():
            s = row.get("status") or "available"
            out[s] = out.get(s, 0) + 1
        out["total"] = sum(v for k, v in out.items() if k != "total")
        return out


def delete_domain_email(email: str) -> bool:
    """从域名邮箱池删除一个邮箱。"""
    with _LOCK:
        rows = _load_domain_pool()
        target = (email or "").lower()
        new_rows = [r for r in rows if (r.get("email") or "").lower() != target]
        if len(new_rows) == len(rows):
            return False
        _save_domain_pool(new_rows)
        return True


# ============================================================
# iCloud Hide My Email pool（本地状态镜像）
# ============================================================

_ICLOUD_HIDE_EMAIL_JSON = _PROJECT_ROOT / "用于注册的iCloud隐藏邮箱.json"


def _load_icloud_hide_pool() -> list[dict]:
    rows = _read_json(_ICLOUD_HIDE_EMAIL_JSON, [])
    return rows if isinstance(rows, list) else []


def _save_icloud_hide_pool(rows: list[dict]) -> None:
    _write_json(_ICLOUD_HIDE_EMAIL_JSON, rows)


def _find_icloud_hide_email(rows: list[dict], email: str) -> dict | None:
    target = (email or "").strip().lower()
    return next((r for r in rows if (r.get("email") or "").strip().lower() == target), None)


def sync_icloud_hide_aliases(aliases: list[dict], account_id: str, *, full_snapshot: bool = True) -> dict:
    """把 sidecar 返回的 HME 别名同步到本地池，保留本地领取/失败状态。"""
    with _LOCK:
        rows = _load_icloud_hide_pool()
        registered = {
            (item.get("email") or "").strip().lower()
            for item in _load_accounts()
            if (item.get("email") or "").strip()
        }
        now = _now()
        inserted = updated = disabled = 0

        remote_emails: set[str] = set()
        for raw in aliases or []:
            email = str(raw.get("email") or "").strip()
            if not email or "@" not in email:
                continue
            remote_emails.add(email.lower())
            active = bool(raw.get("active", True))
            row = _find_icloud_hide_email(rows, email)
            if row is None:
                status = "used" if email.lower() in registered else ("available" if active else "disabled")
                row = {
                    "id": _next_id(rows),
                    "email": email,
                    "status": status,
                    "used_at": now if status == "used" else None,
                    "note": None,
                    "created_at": now,
                }
                rows.append(row)
                inserted += 1
            else:
                updated += 1

            row["account_id"] = str(account_id or "").strip()
            row["anonymous_id"] = str(raw.get("anonymousId") or raw.get("anonymous_id") or "").strip()
            row["label"] = str(raw.get("label") or "").strip()
            row["remote_created_at"] = str(raw.get("createdAt") or raw.get("created_at") or "").strip()
            row["remote_active"] = active
            row["synced_at"] = now

            if email.lower() in registered:
                row["status"] = "used"
                row["used_at"] = row.get("used_at") or now
                row.pop("disabled_reason", None)
            elif not active and row.get("status") == "available":
                row["status"] = "disabled"
                row["disabled_reason"] = "remote_inactive"
                disabled += 1
            elif active and row.get("status") == "disabled" and row.get("disabled_reason") in {"remote_inactive", "remote_missing"}:
                row["status"] = "available"
                row["used_at"] = None
                row.pop("disabled_reason", None)

        if full_snapshot:
            for row in rows:
                if str(row.get("account_id") or "") != str(account_id or ""):
                    continue
                if (row.get("email") or "").strip().lower() in remote_emails:
                    continue
                if row.get("status") == "available":
                    row["status"] = "disabled"
                    row["disabled_reason"] = "remote_missing"
                    row["remote_active"] = False
                    row["synced_at"] = now
                    disabled += 1

        _save_icloud_hide_pool(rows)
        return {
            "inserted": inserted,
            "updated": updated,
            "disabled": disabled,
            "total": len(rows),
        }


def claim_next_icloud_hide_email(account_id: str | None = None) -> dict | None:
    """原子领取一个已同步且仍激活的 iCloud 隐藏邮箱。"""
    with _LOCK:
        rows = sorted(_load_icloud_hide_pool(), key=lambda x: int(x.get("id") or 0))
        row = next((
            item for item in rows
            if item.get("status") == "available"
            and item.get("remote_active", True) is not False
            and (not account_id or str(item.get("account_id") or "") == str(account_id))
        ), None)
        if row is None:
            return None
        row["status"] = "used"
        row["used_at"] = _now()
        row["note"] = None
        _save_icloud_hide_pool(rows)
        return dict(row)


def release_icloud_hide_email(email: str, status: str = "available", note: str | None = None) -> None:
    """更新 HME 别名的本地池状态；不会停用或删除 Apple 侧地址。"""
    with _LOCK:
        rows = _load_icloud_hide_pool()
        row = _find_icloud_hide_email(rows, email)
        if row is None:
            return
        row["status"] = status
        if status == "available":
            row["used_at"] = None
            row.pop("disabled_reason", None)
        elif status in ("used", "failed", "disabled"):
            row["used_at"] = row.get("used_at") or _now()
            if status == "disabled":
                row["disabled_reason"] = "manual"
        if note is not None:
            row["note"] = note
        _save_icloud_hide_pool(rows)


def release_unconsumed_icloud_hide_email(email: str, note: str | None = None) -> bool:
    """原子回收未生成本地账号且仍为 used 的 HME 别名。"""
    with _LOCK:
        if _find_by_email(_load_accounts(), email) is not None:
            return False
        rows = _load_icloud_hide_pool()
        row = _find_icloud_hide_email(rows, email)
        if row is None or row.get("status") != "used" or row.get("remote_active", True) is False:
            return False
        row["status"] = "available"
        row["used_at"] = None
        if note is not None:
            row["note"] = note
        _save_icloud_hide_pool(rows)
        return True


def get_icloud_hide_email_by_email(email: str) -> dict | None:
    with _LOCK:
        row = _find_icloud_hide_email(_load_icloud_hide_pool(), email)
        return dict(row) if row else None


def list_icloud_hide_email_pool(status: str | None = None, limit: int = 500) -> list[dict]:
    with _LOCK:
        rows = sorted(_load_icloud_hide_pool(), key=lambda x: int(x.get("id") or 0), reverse=True)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return [dict(row) for row in rows[:limit]]


def icloud_hide_email_pool_summary() -> dict:
    with _LOCK:
        out: dict[str, int] = {"available": 0, "used": 0, "failed": 0, "disabled": 0}
        for row in _load_icloud_hide_pool():
            status = row.get("status") or "available"
            out[status] = out.get(status, 0) + 1
        out["total"] = sum(value for key, value in out.items() if key != "total")
        return out


def delete_icloud_hide_email(email: str) -> bool:
    """只删除 turb 的本地镜像；Apple 侧别名不受影响，下次同步可能重新出现。"""
    with _LOCK:
        rows = _load_icloud_hide_pool()
        target = (email or "").strip().lower()
        new_rows = [r for r in rows if (r.get("email") or "").strip().lower() != target]
        if len(new_rows) == len(rows):
            return False
        _save_icloud_hide_pool(new_rows)
        return True
