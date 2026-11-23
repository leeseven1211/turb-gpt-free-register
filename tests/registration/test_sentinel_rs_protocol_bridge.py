"""协议模式桥接：密码必须先落库（ack）才允许内核继续。"""
from __future__ import annotations

import json
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from core.kernels.rust.sentinel_rs.bridge import (
    BridgeRequest, SentinelRsFailed, run_registration_protocol,
)

_FAKE = '''#!/usr/bin/env python3
import json, os, sqlite3, sys

def emit(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)

def recv():
    line = sys.stdin.readline()
    if not line:
        raise SystemExit(4)
    return json.loads(line)

args = sys.argv[1:]
if args and args[0] == "--version":
    print("sentinel-rs 0.1.0")
    raise SystemExit(0)

db = args[args.index("--db") + 1]
line = open(os.environ["REG_MAIL_EMAIL_FILE"], encoding="utf-8").read().strip()
email, _ = line.split("----", 1)

emit({"v": 1, "seq": 1, "type": "ready", "data": {"v": 1, "capabilities": ["checkpoint", "landing"]}})
start = recv()
assert start["type"] == "start", start
emit({"v": 1, "seq": 2, "type": "landing", "data": {"verdict": "new", "host": "auth.openai.com"}})
emit({"v": 1, "seq": 3, "type": "checkpoint_prepare",
      "data": {"kind": "password", "email": email, "password": "pw-from-kernel", "challenge_id": "c1"}})
ack = recv()
assert ack["type"] == "checkpoint_ack", ack
if ack["data"]["persisted"] is not True:
    emit({"v": 1, "seq": 4, "type": "progress", "data": {"stage": "login_password", "state": "failed"}})
    raise SystemExit(3)
emit({"v": 1, "seq": 4, "type": "submission",
      "data": {"endpoint": "user/register", "http_status": 200, "receipt": "confirmed"}})
emit({"v": 1, "seq": 5, "type": "otp_request",
      "data": {"challenge_id": "o1", "email": email, "after_ts": 1700000000}})
otp = recv()
assert otp["type"] == "otp_response", otp
assert otp["data"]["challenge_id"] == "o1", otp
if otp["data"]["status"] != "ok" or otp["data"]["code"] != "123456":
    raise SystemExit(5)

con = sqlite3.connect(db)
con.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " email TEXT UNIQUE, password TEXT, access_token TEXT, totp_secret TEXT,"
            " cookies TEXT, status TEXT, created_at INTEGER DEFAULT 0, updated_at INTEGER DEFAULT 0)")
con.execute("INSERT OR REPLACE INTO accounts(email,password,access_token,totp_secret,cookies,status)"
            " VALUES(?,?,?,?,?,?)", (email, "pw-from-kernel", "header.payload.signature", "", "a=b", "registered"))
con.commit()
con.close()
emit({"v": 1, "seq": 5, "type": "progress", "data": {"stage": "token", "state": "success"}})
'''


def _binary(tmp_path: Path) -> Path:
    path = tmp_path / "sentinel-rs"
    path.write_text(_FAKE, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _request(tmp_path: Path) -> BridgeRequest:
    (tmp_path / "run").mkdir(exist_ok=True)
    return BridgeRequest(
        email="fixture@example.test", proxy="socks5h://127.0.0.1:1080",
        code_url="http://mail.invalid/code/token", binary=_binary(tmp_path),
        workdir=tmp_path / "run", timeout_seconds=60, log_level="info",
    )


def test_protocol_bridge_acks_password_before_registration(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_PROTOCOL", "1")
    from core.email import provider as email_provider

    otp_calls = []
    monkeypatch.setattr(
        email_provider, "wait_for_otp",
        lambda address, after_ts, **kwargs: (
            otp_calls.append((address, after_ts)) or "123456"
        ),
    )
    seen = []
    confirmed = []
    stages = []
    account = run_registration_protocol(
        _request(tmp_path),
        on_progress=lambda stage, state, detail: stages.append((stage, state)),
        hooks={
            "persist_password": lambda email, password: (
                seen.append((email, password)) or {"persisted": True, "attempt_id": 7}
            ),
            "confirm_password": lambda: confirmed.append(True),
            "email_source": "generic_api",
        },
    )
    assert otp_calls == [("fixture@example.test", 1700000000.0)]
    assert seen == [("fixture@example.test", "pw-from-kernel")]
    assert confirmed == [True]
    assert ("login_password", "failed") not in stages
    assert account.password == "pw-from-kernel"
    assert account.status == "registered"


def test_protocol_bridge_stops_when_password_is_not_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_PROTOCOL", "1")
    with pytest.raises(SentinelRsFailed):
        run_registration_protocol(
            _request(tmp_path),
            hooks={"persist_password": lambda email, password: {"persisted": False}},
        )
