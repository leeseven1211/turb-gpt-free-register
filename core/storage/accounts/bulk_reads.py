"""只在明确的复制或导出请求中集合读取账号素材。"""
from __future__ import annotations

from core.storage import postgres, records
from psycopg.rows import dict_row

MAX_ID = 2**63 - 1


def database_ids(values):
    """保留可精确定位数据库记录的 ID，非法输入由 HTTP 用例分别列出。"""
    result = []
    for value in values:
        if type(value) is int and 0 < value <= MAX_ID:
            result.append(value)
        elif isinstance(value, str) and value.isascii() and value.isdecimal() and 0 < int(value) <= MAX_ID:
            result.append(int(value))
    return list(dict.fromkeys(result))


def public_id(value):
    """普通数字兼容原响应；超出 JS 安全范围时返回十进制文本。"""
    return str(value) if type(value) is int and abs(value) > 2**53 - 1 else value


def _decode_account(row):
    return records.merge_row(records.ACCOUNTS, row)


def read_accounts(account_ids, *, include_session=False):
    ids = database_ids(account_ids)
    if not ids:
        return {}
    records.init()
    excluded = [] if include_session else ["chatgpt_session"]
    columns = ["id", *(key for key in records.ACCOUNTS.promoted if key not in excluded)]
    selected = ", ".join(postgres.quote_identifier(key) for key in columns)
    with postgres.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {selected}, (data - %s::text[]) AS data "
                    f"FROM {postgres.qualified(records.ACCOUNTS.name)} WHERE id=ANY(%s)",
                    (excluded, ids))
        result = {}
        for raw in cur.fetchall():
            try:
                result[int(raw["id"])] = _decode_account(dict(raw))
            except Exception as exc:
                # 单行历史素材损坏不应丢掉整个 ZIP；不把异常正文或秘密写进结果。
                result[int(raw["id"])] = {"id": int(raw["id"]), "__read_error_type": type(exc).__name__}
        return result


def local_codex_filenames(emails):
    """只读取选中邮箱的未归档凭证文件名，顺序与原列表匹配逻辑相同。"""
    selected = list(dict.fromkeys(str(email or "").strip().lower() for email in emails if str(email or "").strip()))
    if not selected:
        return {}
    records.init()
    with postgres.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT email,filename FROM {postgres.qualified(records.CODEX_CREDENTIALS.name)} "
                    "WHERE archived IS FALSE AND LOWER(BTRIM(COALESCE(email,'')))=ANY(%s) "
                    "ORDER BY COALESCE(mtime,updated_at) DESC,id DESC", (selected,))
        result = {}
        for row in cur.fetchall():
            email = str(row["email"] or "").strip().lower()
            name = str(row["filename"] or "").strip()
            if email and name:
                result.setdefault(email, name)
        return result
