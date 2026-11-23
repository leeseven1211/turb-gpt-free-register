//! 可选的双向 JSON Lines 协议（P1：handshake + checkpoint + landing）。
//! 未设置 `SENTINEL_PROTOCOL=1` 时全部为空操作，CLI 行为不变。
use std::io::{BufRead, Write};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError};
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

const VERSION: u32 = 1;

struct State {
    seq: Mutex<u64>,
    rx: Mutex<Receiver<Value>>,
}

static STATE: OnceLock<State> = OnceLock::new();

pub fn enabled() -> bool {
    matches!(std::env::var("SENTINEL_PROTOCOL").ok().as_deref(), Some("1"))
}

fn state() -> &'static State {
    STATE.get_or_init(|| {
        let (tx, rx) = mpsc::channel::<Value>();
        std::thread::spawn(move || {
            let stdin = std::io::stdin();
            for line in stdin.lock().lines() {
                let Ok(line) = line else { break };
                let line = line.trim();
                if line.is_empty() {
                    continue;
                }
                if let Ok(value) = serde_json::from_str::<Value>(line) {
                    if tx.send(value).is_err() {
                        break;
                    }
                }
            }
        });
        State { seq: Mutex::new(0), rx: Mutex::new(rx) }
    })
}

fn next_seq() -> u64 {
    let state = state();
    let mut seq = state.seq.lock().expect("protocol seq");
    *seq += 1;
    *seq
}

pub fn emit(kind: &str, data: Value) {
    if !enabled() {
        return;
    }
    let message = json!({
        "v": VERSION,
        "seq": next_seq(),
        "type": kind,
        "data": data,
    });
    let mut stdout = std::io::stdout();
    if writeln!(stdout, "{message}").is_ok() {
        let _ = stdout.flush();
    }
}

fn recv(deadline: Duration) -> Result<Value> {
    let state = state();
    let rx = state.rx.lock().expect("protocol recv");
    match rx.recv_timeout(deadline) {
        Ok(value) => Ok(value),
        Err(RecvTimeoutError::Timeout) => bail!("协议等待超时（{}s）", deadline.as_secs()),
        Err(RecvTimeoutError::Disconnected) => bail!("协议管道已关闭"),
    }
}

fn wait_for(kind: &str, timeout: Duration) -> Result<Value> {
    loop {
        let value = recv(timeout)?;
        if value.get("type").and_then(Value::as_str) == Some(kind) {
            return Ok(value);
        }
        // 其它类型（progress/cancel 等）在 P1 先忽略。
    }
}

/// 进程启动后必须先握手：报告能力并等待 Python 的 `start`。
pub fn handshake(expected_email: &str) -> Result<()> {
    if !enabled() {
        return Ok(());
    }
    emit(
        "ready",
        json!({
            "v": VERSION,
            "build": env!("CARGO_PKG_VERSION"),
            "capabilities": ["checkpoint", "landing"],
        }),
    );
    let start = wait_for("start", Duration::from_secs(15)).context("等待 start")?;
    let email = start
        .get("data")
        .and_then(|data| data.get("email"))
        .and_then(Value::as_str)
        .unwrap_or_default();
    if !email.is_empty() && email.to_lowercase() != expected_email.to_lowercase() {
        bail!("start 邮箱与本地分配不一致");
    }
    Ok(())
}

pub fn submission(endpoint: &str, http_status: u16) {
    emit(
        "submission",
        json!({"endpoint": endpoint, "http_status": http_status, "receipt": if http_status == 200 { "confirmed" } else { "rejected" }}),
    );
}

pub fn landing(verdict: &str, host: &str) {
    emit("landing", json!({"verdict": verdict, "host": host}));
}

/// 在发送 `user/register` 之前调用：Python 落库后回 ack，否则禁止继续。
pub fn checkpoint_password(email: &str, password: &str) -> Result<()> {
    if !enabled() {
        return Ok(());
    }
    let challenge = uuid::Uuid::new_v4().to_string();
    emit(
        "checkpoint_prepare",
        json!({"kind": "password", "email": email, "password": password, "challenge_id": challenge}),
    );
    let ack = wait_for("checkpoint_ack", Duration::from_secs(15)).context("等待 checkpoint_ack")?;
    let data = ack.get("data").cloned().unwrap_or_default();
    if data.get("challenge_id").and_then(Value::as_str) != Some(challenge.as_str()) {
        bail!("checkpoint_ack 的 challenge 不匹配");
    }
    if data.get("persisted").and_then(Value::as_bool) != Some(true) {
        bail!("本地未确认密码已落库，拒绝发送 user/register");
    }
    Ok(())
}
