"""显式批量下载的本地凭证快照；不读取历史文件或写入通用任务回执。"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping

from psycopg.rows import dict_row

from core.storage import postgres, records


def read_many(filenames: Iterable[object]) -> dict[str, object]:
    """对所有合法文件名执行一次集合读取，逐项验证留在原下载用例。"""
    from core.storage.db_legacy import _validate_codex_filename

    names = []
    seen = set()
    for value in filenames:
        if not isinstance(value, str):
            continue
        try:
            name = _validate_codex_filename(value)
        except ValueError:
            continue
        if name not in seen:
            seen.add(name)
            names.append(name)
    if not names:
        return {}
    records.init()
    with postgres.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT filename,data->'content' AS content "
            f"FROM {postgres.qualified(records.CODEX_CREDENTIALS.name)} WHERE filename=ANY(%s)",
            (names,),
        )
        return {row["filename"]: row["content"] for row in cur.fetchall()}


def read_credential(snapshot: Mapping[str, object], filename: str) -> tuple[str, str]:
    """沿用单条读取的校验、缺失分类和下载 JSON 格式，只访问已读快照。"""
    from core.storage.db_legacy import _validate_codex_filename

    name = _validate_codex_filename(filename)
    content = snapshot.get(name)
    if not isinstance(content, dict):
        raise ValueError(f"凭证不存在: {name}")
    return json.dumps(content, ensure_ascii=False, indent=2) + "\n", name
