"""Rust 内核桥接只接受进程写回的可核验账号事实。"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from core.kernels.rust.sentinel_rs.bridge import (
    BridgeRequest, SentinelRsFailed, SentinelRsResultInvalid, run_registration,
)


_FAKE = '''#!/usr/bin/env python3
import os
import sqlite3
import sys
import time

args = sys.argv[1:]
if args and args[0] == "--version":
    print("sentinel-rs 0.1.0")
    raise SystemExit(0)

db = args[args.index("--db") + 1]
pool = os.environ["REG_MAIL_EMAIL_FILE"]
line = open(pool, encoding="utf-8").read().strip()
email, code_url = line.split("----", 1)
assert code_url.startswith("http://"), code_url
for marker in ("[1/10] warmup", "[5/10] 密码注册成功", "[7/10] OTP 验证成功"):
    print(marker, flush=True)
status = os.environ.get("FAKE_STATUS", "registered")
token = "" if os.environ.get("FAKE_NO_TOKEN") == "1" else "header.payload.signature"
con = sqlite3.connect(db)
con.execute(
    "CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " email TEXT UNIQUE, password TEXT, access_token TEXT, totp_secret TEXT,"
    " cookies TEXT, status TEXT, created_at INTEGER DEFAULT 0, updated_at INTEGER DEFAULT 0)"
)
con.execute(
    "INSERT OR REPLACE INTO accounts(email,password,access_token,totp_secret,cookies,status)"
    " VALUES(?,?,?,?,?,?)",
    (email, "secret-password", token, "", "a=b; c=d", status),
)
con.commit()
con.close()
print("注册完成", flush=True)
'''


def _binary(tmp_path: Path, body: str = _FAKE) -> Path:
    path = tmp_path / "sentinel-rs"
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _request(tmp_path: Path, binary: Path, **overrides) -> BridgeRequest:
    values = dict(
        email="fixture@example.test", proxy="socks5h://127.0.0.1:1080",
        code_url="http://mail.invalid/code/token", binary=binary,
        workdir=tmp_path / "run", timeout_seconds=60, log_level="info",
    )
    values.update(overrides)
    (tmp_path / "run").mkdir(exist_ok=True)
    return BridgeRequest(**values)


def test_bridge_reads_only_the_verified_account_row(tmp_path):
    binary = _binary(tmp_path)
    stages = []
    account = run_registration(
        _request(tmp_path, binary), on_progress=lambda stage, state, detail: stages.append(stage),
    )
    assert account.email == "fixture@example.test"
    assert account.password == "secret-password"
    assert account.access_token == "header.payload.signature"
    assert account.cookies == "a=b; c=d"
    assert list(dict.fromkeys(stages))[:3] == ["authenticate", "login_password", "email_otp"]


def test_bridge_rejects_a_missing_access_token(tmp_path, monkeypatch):
    binary = _binary(tmp_path)
    monkeypatch.setenv("FAKE_NO_TOKEN", "1")
    with pytest.raises(SentinelRsResultInvalid, match="Access Token"):
        run_registration(_request(tmp_path, binary))


def test_bridge_rejects_a_non_registered_status(tmp_path, monkeypatch):
    binary = _binary(tmp_path)
    monkeypatch.setenv("FAKE_STATUS", "registered_no_token")
    with pytest.raises(SentinelRsResultInvalid, match="registered_no_token"):
        run_registration(_request(tmp_path, binary))


def test_bridge_reports_nonzero_exit_without_leaking_secrets(tmp_path):
    body = _FAKE.split("status = os.environ", 1)[0] + '''
print("失败 password=topsecret token=abc123", flush=True)
raise SystemExit(3)
'''
    binary = _binary(tmp_path, body)
    with pytest.raises(SentinelRsFailed) as caught:
        run_registration(_request(tmp_path, binary))
    assert caught.value.exit_code == 3
    assert "topsecret" not in str(caught.value.diagnostics)
    assert "abc123" not in str(caught.value.diagnostics)



def _pending_db(path: Path, *, email: str = "fixture@example.test", password: str = "pending-pass") -> Path:
    import sqlite3

    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE,"
        " password TEXT, access_token TEXT, totp_secret TEXT, cookies TEXT, status TEXT,"
        " created_at INTEGER DEFAULT 0, updated_at INTEGER DEFAULT 0)"
    )
    con.execute(
        "INSERT INTO accounts(email,password,access_token,totp_secret,cookies,status)"
        " VALUES(?,?,?,?,?,?)",
        (email, password, "", "", "", "pending_otp"),
    )
    con.commit()
    con.close()
    return path


def test_read_accounts_returns_password_before_otp(tmp_path):
    from core.kernels.rust.sentinel_rs.bridge import read_accounts

    db_path = _pending_db(tmp_path / "accounts.db")
    rows = read_accounts(db_path)
    assert [row.email for row in rows] == ["fixture@example.test"]
    assert rows[0].password == "pending-pass"
    assert rows[0].status == "pending_otp"
    assert read_accounts(tmp_path / "missing.db") == []


def test_failed_kernel_saves_generated_password_as_candidate(tmp_path, monkeypatch):
    from core.kernels.rust import sentinel_rs as kernel
    from core.kernels.rust.sentinel_rs.bridge import SentinelRsFailed
    from core.registration import checkpoints

    workdir = tmp_path / "run"
    workdir.mkdir()
    _pending_db(workdir / "accounts.db")
    calls = []

    def fake_save(**kwargs):
        calls.append(kwargs)
        return {"account_id": 1, "state": kwargs["state"]}

    monkeypatch.setattr(checkpoints, "save_protocol_password_checkpoint", fake_save)
    exc = SentinelRsFailed("sentinel-rs 退出码 1", exit_code=1)
    kernel._salvage_kernel_account(
        exc, workdir=workdir, email="fixture@example.test",
        proxy="socks5h://127.0.0.1:1080", email_source="generic_api",
    )
    assert [call["password"] for call in calls] == ["pending-pass"]
    assert calls[0]["state"] == "confirmed"
    assert calls[0]["email_source"] == "generic_api"
    assert exc.password_salvaged is True
    assert exc.kernel_account_status == "pending_otp"


def test_failed_kernel_without_a_row_does_not_fake_a_password(tmp_path, monkeypatch):
    from core.kernels.rust import sentinel_rs as kernel
    from core.kernels.rust.sentinel_rs.bridge import SentinelRsFailed
    from core.registration import checkpoints

    workdir = tmp_path / "run"
    workdir.mkdir()
    calls = []
    monkeypatch.setattr(
        checkpoints, "save_protocol_password_checkpoint", lambda **kwargs: calls.append(kwargs),
    )
    exc = SentinelRsFailed("sentinel-rs 超时", exit_code=None)
    kernel._salvage_kernel_account(
        exc, workdir=workdir, email="fixture@example.test",
        proxy="socks5h://127.0.0.1:1080", email_source="generic_api",
    )
    assert calls == []
    assert not hasattr(exc, "password_salvaged")
