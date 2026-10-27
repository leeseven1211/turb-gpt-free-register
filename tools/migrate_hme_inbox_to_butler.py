#!/usr/bin/env python3
"""默认只读预览 HME 固定路由迁移；显式 --apply 才写入，按回执可回滚。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="执行已明确授权的路由写入；默认只读")
    parser.add_argument("--receipt", type=Path, help="执行时必填：保存原路由映射；不会输出邮箱或密钥")
    parser.add_argument("--rollback", type=Path, help="按给定回执回滚；仍须 --apply")
    parser.add_argument("--include-unpinned-parents", action="store_true", help="同时固定尚无 inbox_profile_id 的 HME 母资源；保留已有其他收件配置")
    args = parser.parse_args(argv)
    if args.apply and not args.rollback and not args.receipt:
        parser.error("迁移执行必须指定 --receipt，以便恢复原固定路由")
    from config import email as cfg
    from core import postgres_store, record_store
    from core.storage.email_inbox_cutover import apply_cutover, plan_cutover, rollback_cutover
    from psycopg.rows import dict_row

    if args.rollback:
        receipt = json.loads(args.rollback.read_text(encoding="utf-8"))
        if not args.apply:
            print(json.dumps({"dry_run": True, "rollback_allocations": receipt["allocation_count"], "rollback_parents": receipt["parent_count"]}))
            return 0
        record_store.init()
        print(json.dumps(rollback_cutover(receipt), ensure_ascii=False))
        return 0
    base = str(cfg.EMAIL_BUTLER_API_BASE or "").strip().rstrip("/")
    mailbox = str(cfg.ICLOUD_HME_FORWARD_IMAP_EMAIL or "").strip().lower()
    key = str(cfg.EMAIL_BUTLER_API_KEY or "").strip()
    if not key:
        parser.error("EMAIL_BUTLER_API_KEY 未配置")
    identity = hashlib.sha256(f"butler:{base}:{mailbox}".encode()).hexdigest()
    version = hashlib.sha256(f"{identity}:{key}".encode()).hexdigest()
    reference = f"EMAIL_DERIVATION_BUTLER_SECRET_{version[:20].upper()}"
    if args.apply:
        # 初始化会执行 DDL，必须在预览 SELECT 或迁移行锁的事务之前完成。
        record_store.init()
    with postgres_store.connect(row_factory=dict_row) as conn:
        if not args.apply:
            conn.execute("SET TRANSACTION READ ONLY")
        plan = plan_cutover(api_base=base, mailbox_email=mailbox, credential_ref=reference,
            include_unpinned_parents=args.include_unpinned_parents, conn=conn)
        if args.apply:
            # 凭据只进入 .env；即使 PG 事务失败也保留此版本，不覆盖旧凭据。
            from core.email_derivation import _save_profile_secret
            _save_profile_secret(reference, key)
            receipt = apply_cutover(plan, conn=conn)
            target = args.receipt.expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(receipt, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
    print(json.dumps({"dry_run": not args.apply, "allocation_count": plan["allocation_count"], "parent_count": plan["parent_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
