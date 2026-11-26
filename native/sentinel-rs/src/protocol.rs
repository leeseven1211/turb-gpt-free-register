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

/// 单轮验证码等待秒数（与 Python `OTP_MAX_WAIT` 同源，由桥接写入环境变量）。
pub fn otp_max_wait_seconds() -> u64 {
    std::env::var("OTP_MAX_WAIT")
        .ok()
        .and_then(|raw| raw.trim().parse::<u64>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(300)
}

/// 超时后的重发次数（与 Python `OTP_RESEND_COUNT` 同源）。
pub fn otp_resend_count() -> u32 {
    std::env::var("OTP_RESEND_COUNT")
        .ok()
        .and_then(|raw| raw.trim().parse::<u32>().ok())
        .unwrap_or(1)
}

/// Python 落库可能要等数据库锁；默认 180s，可用环境变量收紧/放宽。
fn checkpoint_ack_timeout() -> Duration {
    let seconds = std::env::var("SENTINEL_CHECKPOINT_ACK_TIMEOUT_SECONDS")
        .ok()
        .and_then(|raw| raw.trim().parse::<u64>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(180);
    Duration::from_secs(seconds)
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
    if !expected_email.is_empty() && !email.is_empty()
        && email.to_lowercase() != expected_email.to_lowercase()
    {
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

/// 刷新 AT 的握手：报告 `refresh` 能力并等待带完整参数的 `start`。
///
/// 与注册的 [`handshake`] 分开：注册只校验邮箱一致，刷新需要把 Cookie、
/// 设备指纹和账号身份一次交付给内核。
pub fn handshake_refresh() -> Result<Value> {
    if !enabled() {
        bail!("协议模式未启用");
    }
    emit(
        "ready",
        json!({
            "v": VERSION,
            "build": env!("CARGO_PKG_VERSION"),
            "capabilities": ["refresh", "otp", "session_reuse", "cookie_restore"],
        }),
    );
    let start = wait_for("start", Duration::from_secs(60)).context("等待 start")?;
    Ok(start.get("data").cloned().unwrap_or_default())
}

/// 有界阶段事件（不含凭据/正文）。
pub fn progress(stage: &str, state: &str, detail: Option<&str>) {
    emit(
        "progress",
        json!({"stage": stage, "state": state, "detail": detail}),
    );
}

/// 成功终态。
pub fn result_ok(data: Value) {
    emit("result", data);
}

/// 失败终态；字段与 Python 侧 v3 的错误分类保持同名。
pub fn result_partial(data: Value) {
    emit("result_partial", data);
}

/// 协议模式下向 Python 请求验证码；Python 用自己的邮箱服务等待并回传。
///
/// 这里是单轮等待：`timeout` 到了返回 `Ok(None)`，由调用方决定是否重发。
pub fn request_otp_window(
    email: &str,
    after_ts: u64,
    timeout: Duration,
) -> Result<Option<String>> {
    if !enabled() {
        bail!("协议模式未启用");
    }
    let challenge = uuid::Uuid::new_v4().to_string();
    emit(
        "otp_request",
        json!({"challenge_id": challenge, "email": email, "after_ts": after_ts}),
    );
    let deadline = std::time::Instant::now() + timeout;
    loop {
        let remaining = deadline.saturating_duration_since(std::time::Instant::now());
        if remaining.is_zero() {
            return Ok(None);
        }
        let value = match recv(remaining) {
            Ok(value) => value,
            Err(_) => return Ok(None),
        };
        if value.get("type").and_then(Value::as_str) != Some("otp_response") {
            continue;
        }
        let data = value.get("data").cloned().unwrap_or_default();
        if data.get("challenge_id").and_then(Value::as_str) != Some(challenge.as_str()) {
            continue;
        }
        let status = data.get("status").and_then(Value::as_str).unwrap_or("malformed");
        if status == "timeout" {
            return Ok(None);
        }
        if status != "ok" {
            bail!("取码失败（Python 侧）：{status}");
        }
        let code = data.get("code").and_then(Value::as_str).unwrap_or_default().to_string();
        if code.len() != 6 || !code.chars().all(|ch| ch.is_ascii_digit()) {
            bail!("取码结果不是 6 位数字");
        }
        return Ok(Some(code));
    }
}

/// 兼容旧调用：单轮等待固定 1200 秒，超时报错。
pub fn request_otp(email: &str, after_ts: u64) -> Result<String> {
    match request_otp_window(email, after_ts, Duration::from_secs(1200))? {
        Some(code) => Ok(code),
        None => bail!("等待邮箱验证码超时（Python 侧）"),
    }
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
    let ack = wait_for("checkpoint_ack", checkpoint_ack_timeout()).context("等待 checkpoint_ack")?;
    let data = ack.get("data").cloned().unwrap_or_default();
    if data.get("challenge_id").and_then(Value::as_str) != Some(challenge.as_str()) {
        bail!("checkpoint_ack 的 challenge 不匹配");
    }
    if data.get("persisted").and_then(Value::as_bool) != Some(true) {
        bail!("本地未确认密码已落库，拒绝发送 user/register");
    }
    Ok(())
}
