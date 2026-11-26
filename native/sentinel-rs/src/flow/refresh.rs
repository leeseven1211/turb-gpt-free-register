//! AT 刷新内核（protocol v3 等价）。
//!
//! 两条路径：
//! 1. **快路径**：用 Python 交付的私有会话 Cookie 直接 `GET /api/auth/session`；
//!    身份核验通过就返回，不登录。
//! 2. **重登**：快路径失败后走 warmup → signin → authorize → 页面状态机
//!    （密码 / 邮箱验证码 / TOTP / workspace / callback）→ session。
//!
//! 与注册的差异（刻意保留）：
//! * 只读不写：不建号、不设密码、不 enroll 2FA；
//! * OTP 由 Python 取码（`crate::protocol::request_otp`），内核不碰邮箱；
//! * 凭据只走协议私有通道，不写日志、不写 SQLite。
//!
//! 安全边界：密码 / OTP / Cookie / AT 只出现在内存与 `result` 消息里；
//! `progress` 只带阶段名。

use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use super::auth::{self, AuthRequestBuilder};
use super::http::{self, CookieSnapshot, RequestSpec};
use super::twofa;
use super::SentinelTokenSource;

const AUTH_BASE: &str = auth::AUTH_BASE;
const CHAT_BASE: &str = auth::CHATGPT_BASE;
const TRUSTED_HOSTS: [&str; 2] = ["auth.openai.com", "chatgpt.com"];
const COOKIE_HOSTS: [&str; 3] = ["auth.openai.com", "chatgpt.com", "sentinel.openai.com"];
const MAX_LOOP: usize = 8;
const MAX_REDIRECTS: usize = 12;

// ─────────────────────────── 入参 ───────────────────────────

/// Python 私有会话缓存里的单条 Cookie（字段与 `_restore_cookies` 一致）。
#[derive(Debug, Clone, Deserialize, Serialize, Default)]
pub struct CookieSeed {
    pub name: String,
    pub value: String,
    #[serde(default)]
    pub domain: String,
    #[serde(default)]
    pub path: String,
    #[serde(default)]
    pub secure: bool,
    #[serde(default)]
    pub expires: Option<i64>,
}

/// 一次刷新所需的全部事实；全部由 Python 交付，内核不自行取账号。
#[derive(Debug, Clone, Deserialize, Default)]
pub struct RefreshConfig {
    pub email: String,
    #[serde(default)]
    pub password: String,
    #[serde(default)]
    pub totp_secret: String,
    /// 上次登录的 `oai-did`；为空时从 Cookie 读，再为空则随机生成。
    #[serde(default)]
    pub device_id: String,
    /// 账号已知身份（用户/组织），用于核验登录结果。
    #[serde(default)]
    pub user_id: String,
    #[serde(default)]
    pub account_id: String,
    #[serde(default)]
    pub proxy: Option<String>,
    /// `ACCOUNT_AT_REFRESH_COUNTRY` 解析结果；只影响指纹档位。
    #[serde(default)]
    pub country: Option<String>,
    #[serde(default)]
    pub cookies: Vec<CookieSeed>,
    #[serde(default)]
    pub user_agent: Option<String>,
    #[serde(default)]
    pub accept_language: Option<String>,
}

/// 成功结果：只带刷新事实，不带密码。
#[derive(Debug, Clone, Default, Serialize)]
pub struct RefreshOutcome {
    pub access_token: String,
    pub session: Value,
    pub cookies: Vec<CookieSnapshot>,
    pub session_reused: bool,
    pub methods: Vec<String>,
    pub device_id: String,
}

// ─────────────────────────── 错误 ───────────────────────────

/// 与 v3 `ProtocolV2AuthError` 同名的分类错误；Python 侧按 code/category 归一。
#[derive(Debug, Clone)]
pub struct RefreshError {
    pub code: String,
    pub category: String,
    pub retryable: bool,
    pub roxy_fallback_allowed: bool,
    pub http_status: Option<u16>,
    pub detail: String,
}

impl RefreshError {
    pub fn new(code: &str, category: &str) -> Self {
        Self {
            code: code.to_string(),
            category: category.to_string(),
            retryable: false,
            roxy_fallback_allowed: true,
            http_status: None,
            detail: String::new(),
        }
    }

    pub fn retryable(mut self, value: bool) -> Self {
        self.retryable = value;
        self
    }

    pub fn no_roxy(mut self) -> Self {
        self.roxy_fallback_allowed = false;
        self
    }

    pub fn status(mut self, value: u16) -> Self {
        self.http_status = Some(value);
        self
    }

    pub fn detail(mut self, value: impl Into<String>) -> Self {
        self.detail = value.into();
        self
    }

    pub fn to_json(&self) -> Value {
        json!({
            "ok": false,
            "status": if self.code == "account_deactivated" { "deactivated" } else { "failed" },
            "error": self.code,
            "error_code": self.code,
            "error_category": self.category,
            "retryable": self.retryable,
            "roxy_fallback_allowed": self.roxy_fallback_allowed,
            "http_status": self.http_status,
            "detail": self.detail,
        })
    }
}

impl std::fmt::Display for RefreshError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if self.detail.is_empty() {
            write!(f, "{}", self.code)
        } else {
            write!(f, "{}: {}", self.code, self.detail)
        }
    }
}

impl std::error::Error for RefreshError {}

fn err(code: &str, category: &str) -> RefreshError {
    RefreshError::new(code, category)
}

// ─────────────────────────── 入口 ───────────────────────────

/// 执行一次刷新。`sentinel` 与注册共用，flow 名用 `password_verify`。
pub async fn refresh_once(
    cfg: &RefreshConfig,
    sentinel: &dyn SentinelTokenSource,
) -> Result<RefreshOutcome> {
    if cfg.email.trim().is_empty() {
        bail!("refresh.email 不能为空");
    }
    let email = cfg.email.trim().to_string();
    let ua = cfg
        .user_agent
        .clone()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| super::DEFAULT_USER_AGENT.to_string());
    let lang = cfg
        .accept_language
        .clone()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| super::DEFAULT_ACCEPT_LANGUAGE.to_string());

    // 指纹：有 device_id 时用它当 seed，保证同一账号画像稳定。
    let fp = crate::fingerprint::DeviceFingerprint::generate_for_country(
        Some(cfg.device_id.trim()).filter(|value| !value.is_empty()),
        cfg.country.as_deref(),
    );
    let emulation = http::parse_emulation(&fp.emulation);

    let client = http::Client::build_with_emulation(
        &ua,
        cfg.proxy.as_deref(),
        http::RetryPolicy::default(),
        emulation,
    )?;

    // 1) 注入会话 Cookie（过期/异域的直接丢弃）。
    let now = now_ts();
    let mut injected = 0usize;
    for item in &cfg.cookies {
        let domain = item.domain.trim().trim_start_matches('.').to_ascii_lowercase();
        if !COOKIE_HOSTS.contains(&domain.as_str()) {
            continue;
        }
        if let Some(expires) = item.expires {
            if expires <= now {
                continue;
            }
        }
        client
            .add_cookie(&item.name, &item.value, &item.domain, &item.path, item.secure)
            .ok();
        injected += 1;
    }
    let mut device_id = cfg.device_id.trim().to_string();
    if device_id.is_empty() {
        for item in &cfg.cookies {
            if item.name.eq_ignore_ascii_case("oai-did") && !item.value.trim().is_empty() {
                device_id = item.value.trim().to_string();
                break;
            }
        }
    }
    if device_id.is_empty() {
        device_id = uuid::Uuid::new_v4().to_string();
    }
    let builder = AuthRequestBuilder::new(&ua, &lang, &device_id).with_fingerprint(&fp);

    // 2) 快路径：只读会话，不登录。
    if injected > 0 {
        crate::protocol::progress("session_cache", "running", Some("复用已保存的登录会话"));
        match read_session(&client, &builder, true).await {
            Ok(Some(info)) => {
                verify_identity(&info, &email, cfg)?;
                let outcome = build_outcome(&client, &builder, info, true, vec!["session_cookie".into()], &device_id);
                crate::protocol::progress("session_cache", "success", Some("会话有效，已取得新 AT"));
                crate::protocol::progress("token", "success", Some("已取得并核验最新 AT"));
                return Ok(outcome);
            }
            Ok(None) => {
                crate::protocol::progress("session_cache", "failed", Some("会话已失效，转入重新登录"));
            }
            Err(error) => {
                if error.code == "cached_session_network_failed"
                    || error.code == "cached_session_http_failed"
                {
                    return Err(error.into());
                }
                crate::protocol::progress("session_cache", "failed", Some("会话不可用，转入重新登录"));
            }
        }
    }

    // 3) 重登：warmup → signin → authorize。
    crate::protocol::progress("authenticate", "running", Some("开始重新登录"));
    let probe = builder_for_merge(&ua, &lang, "");
    let warm = super::authorize::warmup(&client, &probe)
        .await
        .map_err(|error| {
            err("network_preflight_failed", "network")
                .retryable(true)
                .detail(error.to_string())
        })?;
    if device_id.is_empty() || device_id != warm.device_id {
        device_id = warm.device_id.clone();
    }
    let builder = AuthRequestBuilder::new(&ua, &lang, &device_id).with_fingerprint(&fp);
    let auth_url = super::authorize::fetch_authorize_url(
        &client,
        &builder,
        &email,
        &warm.csrf_token,
        &device_id,
    )
    .await
    .map_err(|error| {
        err("network_preflight_failed", "network")
            .retryable(true)
            .detail(error.to_string())
    })?;
    let init = super::authorize::auth_oauth_init(&client, &builder, &auth_url, &device_id)
        .await
        .map_err(|error| {
            err("network_preflight_failed", "network")
                .retryable(true)
                .detail(error.to_string())
        })?;

    let (info, methods) = authenticate(
        &client,
        &builder,
        &init.landing_url,
        &email,
        cfg,
        sentinel,
        &device_id,
    )
    .await?;
    verify_identity(&info, &email, cfg)?;
    let outcome = build_outcome(&client, &builder, info, false, methods, &device_id);
    crate::protocol::progress("token", "success", Some("已取得并核验最新 AT"));
    Ok(outcome)
}

fn builder_for_merge(ua: &str, lang: &str, device_id: &str) -> AuthRequestBuilder {
    AuthRequestBuilder::new(ua, lang, device_id)
}

fn build_outcome(
    client: &http::Client,
    _builder: &AuthRequestBuilder,
    info: Value,
    reused: bool,
    methods: Vec<String>,
    device_id: &str,
) -> RefreshOutcome {
    let access_token = info
        .get("accessToken")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();
    RefreshOutcome {
        access_token,
        session: info,
        cookies: filtered_cookies(client),
        session_reused: reused,
        methods,
        device_id: device_id.to_string(),
    }
}

fn filtered_cookies(client: &http::Client) -> Vec<CookieSnapshot> {
    let now = now_ts();
    client
        .cookie_snapshot()
        .into_iter()
        .filter(|item| {
            let domain = item.domain.trim().trim_start_matches('.').to_ascii_lowercase();
            COOKIE_HOSTS.contains(&domain.as_str())
                && item.expires.map(|expires| expires > now).unwrap_or(true)
        })
        .collect()
}

// ─────────────────────────── 登录状态机 ───────────────────────────

async fn authenticate(
    client: &http::Client,
    builder: &AuthRequestBuilder,
    initial_url: &str,
    email: &str,
    cfg: &RefreshConfig,
    sentinel: &dyn SentinelTokenSource,
    device_id: &str,
) -> Result<(Value, Vec<String>), RefreshError> {
    let mut methods: Vec<String> = Vec::new();
    let mut seen: Vec<String> = Vec::new();
    let mut password_probe_attempted = false;
    let mut payload = json!({"continue_url": initial_url});

    for _ in 0..MAX_LOOP {
        if let Some(context) = auth_context_from_cookie(client) {
            if let Value::Object(map) = &mut payload {
                map.insert("oai-client-auth-session".into(), context);
            }
        }
        let url = continue_url(&payload);
        let kind = page_kind(&payload);
        let path = url_path(&url);
        let stage = classify_stage(&kind, &path)?;

        // 密码页探测：只在邮箱验证码页、且本地存有密码时试一次。
        if stage == "email_otp"
            && !cfg.password.is_empty()
            && !seen.iter().any(|item| item == "password")
            && !password_probe_attempted
        {
            password_probe_attempted = true;
            let offered = follow(client, builder, &format!("{AUTH_BASE}/log-in/password"), &url).await;
            match offered {
                Ok(final_url) if url_path(&final_url) == "/log-in/password" => {
                    payload = json!({"continue_url": final_url});
                    continue;
                }
                Ok(_) => {}
                Err(error) if error.code == "auth_navigation_failed" && error.http_status == Some(404) => {}
                Err(error) => return Err(error),
            }
        }

        if seen.iter().any(|item| item == &stage) {
            return Err(err("auth_challenge_loop", "response"));
        }
        seen.push(stage.clone());

        match stage.as_str() {
            "password" => {
                if cfg.password.is_empty() {
                    return Err(err("password_missing", "configuration").no_roxy());
                }
                crate::protocol::progress("password", "running", None);
                let token = sentinel
                    .token("password_verify", device_id)
                    .map_err(|error| {
                        err("password_sentinel_failed", "network")
                            .retryable(true)
                            .detail(error.to_string())
                    })?;
                let spec = builder.password_verify_login(&cfg.password, &token);
                payload = post_json(client, &spec, "password_verify").await?;
                methods.push("password".into());
                crate::protocol::progress("password", "success", None);
            }
            "email_otp" => {
                crate::protocol::progress("email_otp", "running", None);
                let _ = client.execute(&builder.otp_send()).await;
                let attempts = 1 + crate::protocol::otp_resend_count();
                let wait_secs = crate::protocol::otp_max_wait_seconds();
                let mut received = None;
                for attempt in 1..=attempts {
                    let after_ts = now_ts_u64();
                    match crate::protocol::request_otp_window(
                        email,
                        after_ts,
                        std::time::Duration::from_secs(wait_secs),
                    )
                    .map_err(|error| {
                        err("email_otp_failed", "email").detail(error.to_string())
                    })? {
                        Some(code) => {
                            received = Some(code);
                            break;
                        }
                        None => {
                            if attempt < attempts {
                                crate::protocol::progress(
                                    "email_otp",
                                    "running",
                                    Some("等待超时，正在重发验证码"),
                                );
                                let _ = client.execute(&builder.otp_send()).await;
                            }
                        }
                    }
                }
                let code = received.ok_or_else(|| {
                    err("email_otp_failed", "email").detail(format!(
                        "等待邮箱验证码超时（已重发 {} 次）",
                        attempts - 1
                    ))
                })?;
                let spec = builder.otp_validate(&code);
                payload = post_json(client, &spec, "email_otp_validate").await?;
                methods.push("email_otp".into());
                crate::protocol::progress("email_otp", "success", None);
            }
            "mfa" => {
                if cfg.totp_secret.is_empty() {
                    return Err(err("mfa_secret_missing", "configuration").no_roxy());
                }
                crate::protocol::progress("mfa_challenge", "running", None);
                let factor = factor_id(&payload, &url);
                if factor.is_empty() {
                    return Err(err("mfa_factor_missing", "response"));
                }
                let _ = post_json(client, &builder.mfa_issue_challenge(&factor), "mfa_issue_challenge").await?;
                wait_totp_window().await;
                let code = twofa::totp_now(&cfg.totp_secret)
                    .map_err(|error| err("mfa_secret_invalid", "configuration").no_roxy().detail(error.to_string()))?;
                payload = post_json(client, &builder.mfa_verify_login(&factor, &code), "mfa_verify").await?;
                methods.push("mfa".into());
                crate::protocol::progress("mfa_challenge", "success", None);
            }
            "workspace" => {
                crate::protocol::progress("workspace", "running", None);
                let workspace = workspace_id(&payload, &cfg.account_id)?;
                let spec = builder.select_workspace(&workspace);
                payload = post_json(client, &spec, "workspace_select").await?;
            }
            "callback" => {
                let final_url = follow(client, builder, &url, &format!("{CHAT_BASE}/")).await?;
                let final_path = url_path(&final_url);
                if final_path == "/about-you"
                    || final_path == "/log-in/password"
                    || final_path == "/email-verification"
                    || final_path == "/workspace"
                    || final_path.starts_with("/mfa-challenge")
                {
                    payload = json!({"continue_url": final_url});
                    seen.retain(|item| item != "callback");
                    continue;
                }
                if url_host(&final_url) != "chatgpt.com" {
                    return Err(err("auth_page_unknown", "response"));
                }
                let info = read_session(client, builder, false)
                    .await?
                    .ok_or_else(|| err("session_invalid_response", "response"))?;
                if methods.is_empty() {
                    methods.push("existing_session".into());
                }
                return Ok((info, methods));
            }
            "account_profile_required" => {
                return Err(err("account_profile_required", "account").no_roxy());
            }
            other => {
                return Err(err("auth_page_unknown", "response").detail(other.to_string()));
            }
        }
    }
    Err(err("auth_challenge_loop", "response"))
}

fn classify_stage(kind: &str, path: &str) -> Result<String, RefreshError> {
    if matches!(kind, "about_you" | "about-you" | "create_account" | "create-account")
        || matches!(path, "/about-you" | "/create-account/password" | "/create-account")
    {
        return Ok("account_profile_required".into());
    }
    if kind.contains("mfa") || path.starts_with("/mfa-challenge") {
        return Ok("mfa".into());
    }
    if kind == "workspace" || path == "/workspace" {
        return Ok("workspace".into());
    }
    if path == "/log-in/password"
        || matches!(kind, "password" | "login_password" | "password_verify")
    {
        return Ok("password".into());
    }
    if path == "/email-verification" || matches!(kind, "email_otp" | "email_verification") {
        return Ok("email_otp".into());
    }
    if path.is_empty() {
        return Err(err("auth_page_unknown", "response"));
    }
    Ok("callback".into())
}

// ─────────────────────────── HTTP 原语 ───────────────────────────

/// `POST` JSON 并返回响应对象；非 2xx 映射成可分类错误。
async fn post_json(
    client: &http::Client,
    spec: &RequestSpec,
    operation: &str,
) -> Result<Value, RefreshError> {
    let response = client.execute(spec).await.map_err(|error| {
        err(&format!("{operation}_failed"), "network")
            .retryable(true)
            .detail(error.to_string())
    })?;
    if !(200..300).contains(&response.status) {
        // 密码被明确拒绝/要求改密：这是账号凭据决定，不是网络故障，也不该自动回落浏览器。
        let parsed: Option<Value> = serde_json::from_str(&response.body).ok();
        let api_code = parsed
            .as_ref()
            .and_then(|value| value.pointer("/error/code").or_else(|| value.get("code")))
            .and_then(Value::as_str)
            .unwrap_or_default()
            .trim()
            .to_string();
        if api_code == "password_reset_required" {
            return Err(err("password_change_required", "auth")
                .no_roxy()
                .status(response.status)
                .detail(snippet(&response.body)));
        }
        if operation == "password_verify" && matches!(response.status, 400 | 401) {
            return Err(err("password_rejected", "auth")
                .no_roxy()
                .status(response.status)
                .detail(snippet(&response.body)));
        }
        return Err(err(&format!("{operation}_failed"), "network")
            .retryable(matches!(response.status, 403 | 429) || response.status >= 500)
            .status(response.status)
            .detail(snippet(&response.body)));
    }
    let value: Value = serde_json::from_str(&response.body).map_err(|_| {
        err(&format!("{operation}_invalid_response"), "response").detail(snippet(&response.body))
    })?;
    if !value.is_object() {
        return Err(err(&format!("{operation}_invalid_response"), "response"));
    }
    // 提交已发生但结构不符：保留可核对事实。
    Ok(value)
}

/// 跟随重定向（最多 12 跳），只允许 https + 白名单 host。
async fn follow(
    client: &http::Client,
    builder: &AuthRequestBuilder,
    url: &str,
    referer: &str,
) -> Result<String, RefreshError> {
    let mut current = trusted_url(url, AUTH_BASE)?;
    let mut referer = referer.to_string();
    for _ in 0..MAX_REDIRECTS {
        let spec = builder.navigation_from(&current, &referer);
        let response = client.execute(&spec).await.map_err(|error| {
            err("auth_navigation_failed", "network")
                .retryable(true)
                .detail(error.to_string())
        })?;
        if matches!(response.status, 301 | 302 | 303 | 307 | 308) {
            let location = response
                .header("location")
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .ok_or_else(|| err("auth_redirect_invalid", "response"))?;
            let next = trusted_url(location, &current)?;
            referer = current;
            current = next;
            continue;
        }
        if !(200..300).contains(&response.status) {
            return Err(err("auth_navigation_failed", "network")
                .retryable(matches!(response.status, 403 | 429) || response.status >= 500)
                .status(response.status)
                .detail(snippet(&response.body)));
        }
        return Ok(current);
    }
    Err(err("auth_redirect_limit", "response"))
}

/// 读会话：`Ok(None)` 表示“缓存码无效，可重登”，其它失败返回错误。
async fn read_session(
    client: &http::Client,
    builder: &AuthRequestBuilder,
    cached: bool,
) -> Result<Option<Value>, RefreshError> {
    let response = client
        .execute(&builder.chat_session_nextauth())
        .await
        .map_err(|error| {
            err(
                if cached { "cached_session_network_failed" } else { "session_fetch_failed" },
                "network",
            )
            .retryable(true)
            .detail(error.to_string())
        })?;
    if cached && response.status == 401 {
        return Ok(None);
    }
    if !(200..300).contains(&response.status) {
        return Err(err(
            if cached { "cached_session_http_failed" } else { "session_fetch_failed" },
            "network",
        )
        .retryable(matches!(response.status, 403 | 429) || response.status >= 500)
        .status(response.status)
        .detail(snippet(&response.body)));
    }
    let info: Value = serde_json::from_str(&response.body).map_err(|_| {
        err(
            if cached { "cached_session_invalid_response" } else { "session_invalid_response" },
            "response",
        )
    })?;
    if !info.is_object() {
        return Err(err(
            if cached { "cached_session_invalid_response" } else { "session_invalid_response" },
            "response",
        ));
    }
    let token = info
        .get("accessToken")
        .and_then(Value::as_str)
        .unwrap_or_default();
    if token.trim().is_empty() {
        if cached {
            return Ok(None);
        }
        return Err(err("access_token_missing", "response"));
    }
    if token_expired(token) {
        return Err(err("access_token_expired", "auth"));
    }
    Ok(Some(info))
}

// ─────────────────────────── 身份与页面事实 ───────────────────────────

fn verify_identity(info: &Value, email: &str, cfg: &RefreshConfig) -> Result<(), RefreshError> {
    let user = info.get("user").cloned().unwrap_or(Value::Null);
    let account = info.get("account").cloned().unwrap_or(Value::Null);
    let user_email = user
        .get("email")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .trim()
        .to_string();
    if user_email.is_empty() {
        return Err(err("identity_unconfirmed", "response").no_roxy());
    }
    if !user_email.eq_ignore_ascii_case(email.trim()) {
        return Err(err("identity_mismatch", "account").no_roxy());
    }
    let user_id = user.get("id").and_then(Value::as_str).unwrap_or_default();
    let account_id = account.get("id").and_then(Value::as_str).unwrap_or_default();
    if (!cfg.user_id.trim().is_empty() && user_id != cfg.user_id.trim())
        || (!cfg.account_id.trim().is_empty() && account_id != cfg.account_id.trim())
    {
        return Err(err("identity_mismatch", "account").no_roxy());
    }
    let token = info
        .get("accessToken")
        .and_then(Value::as_str)
        .unwrap_or_default();
    if let Some(claims) = jwt_claims(token) {
        let auth = claims
            .get("https://api.openai.com/auth")
            .cloned()
            .unwrap_or(Value::Null);
        let profile = claims
            .get("https://api.openai.com/profile")
            .cloned()
            .unwrap_or(Value::Null);
        let claim_email = profile
            .get("email")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .trim()
            .to_string();
        let claim_user = auth
            .get("chatgpt_user_id")
            .or_else(|| auth.get("user_id"))
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();
        let claim_account = auth
            .get("chatgpt_account_id")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();
        if (!claim_email.is_empty() && !claim_email.eq_ignore_ascii_case(email.trim()))
            || (!claim_user.is_empty() && claim_user != user_id)
            || (!claim_account.is_empty() && claim_account != account_id)
        {
            return Err(err("identity_mismatch", "account").no_roxy());
        }
    }
    Ok(())
}

/// `oai-client-auth-session` 只在服务端挑战时用；取不到就是空。
fn auth_context_from_cookie(client: &http::Client) -> Option<Value> {
    let jar = client.cookie_header_for(AUTH_BASE);
    let raw = auth::cookie_value(&jar, "oai-client-auth-session")?;
    for segment in raw.split('.').take(2) {
        let Ok(bytes) = base64url_decode(segment) else {
            continue;
        };
        let Ok(decoded) = serde_json::from_slice::<Value>(&bytes) else {
            continue;
        };
        let value = decoded
            .get("oai-client-auth-session")
            .cloned()
            .unwrap_or(decoded);
        if value.is_object() {
            return Some(value);
        }
    }
    None
}

fn continue_url(payload: &Value) -> String {
    let page = payload.get("page").cloned().unwrap_or(Value::Null);
    let nested = page.get("payload").cloned().unwrap_or(Value::Null);
    let value = payload
        .get("continue_url")
        .or_else(|| payload.get("external_url"))
        .or_else(|| payload.get("url"))
        .or_else(|| page.get("continue_url"))
        .or_else(|| page.get("external_url"))
        .or_else(|| page.get("url"))
        .or_else(|| nested.get("url"))
        .and_then(Value::as_str)
        .unwrap_or_default();
    if value.is_empty() {
        String::new()
    } else {
        auth::absolute_url(value, AUTH_BASE)
    }
}

fn page_kind(payload: &Value) -> String {
    payload
        .get("page")
        .and_then(|page| page.get("type"))
        .and_then(Value::as_str)
        .unwrap_or_default()
        .trim()
        .to_ascii_lowercase()
}

fn factor_id(payload: &Value, url: &str) -> String {
    let page = payload.get("page").cloned().unwrap_or(Value::Null);
    let nested = page.get("payload").cloned().unwrap_or(Value::Null);
    let candidates = [
        payload.get("factor_id"),
        payload.get("factorId"),
        payload.get("id"),
        page.get("factor_id"),
        page.get("factorId"),
        nested.get("factor_id"),
        nested.get("factorId"),
        nested.get("id"),
    ];
    for item in candidates.iter().flatten() {
        if let Some(value) = item.as_str() {
            if !value.trim().is_empty() {
                return value.trim().to_string();
            }
        }
    }
    if let Some(last) = url.trim_end_matches('/').rsplit('/').next() {
        if url.contains("/mfa-challenge/") && !last.is_empty() {
            return last.to_string();
        }
    }
    String::new()
}

fn workspace_id(payload: &Value, expected_account: &str) -> Result<String, RefreshError> {
    let page = payload.get("page").cloned().unwrap_or(Value::Null);
    let context = payload.get("oai-client-auth-session").cloned().unwrap_or(Value::Null);
    let mut candidates = context
        .get("workspaces")
        .cloned()
        .unwrap_or(Value::Null);
    if candidates.is_null() {
        candidates = page
            .get("payload")
            .and_then(|nested| nested.get("workspaces"))
            .cloned()
            .unwrap_or(Value::Null);
    }
    let items: Vec<Value> = candidates
        .as_array()
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|item| item.get("id").and_then(Value::as_str).is_some())
        .collect();
    let expected = expected_account.trim();
    if !expected.is_empty() {
        let matched: Vec<String> = items
            .iter()
            .filter(|item| {
                let id = item.get("id").and_then(Value::as_str).unwrap_or_default();
                let account = item.get("account_id").and_then(Value::as_str).unwrap_or_default();
                id == expected || account == expected
            })
            .filter_map(|item| item.get("id").and_then(Value::as_str).map(str::to_string))
            .collect();
        if matched.len() == 1 {
            return Ok(matched[0].clone());
        }
    }
    let mut unique: Vec<String> = Vec::new();
    for item in &items {
        if let Some(id) = item.get("id").and_then(Value::as_str) {
            if !unique.iter().any(|value| value == id) {
                unique.push(id.to_string());
            }
        }
    }
    if unique.len() == 1 {
        return Ok(unique[0].clone());
    }
    Err(err(
        if unique.is_empty() { "workspace_missing" } else { "workspace_ambiguous" },
        "response",
    ))
}

async fn wait_totp_window() {
    // 最后 6 秒不提交，避免跨窗失效（对齐 v2 `_totp_code`）。
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|value| value.as_secs_f64())
        .unwrap_or(0.0);
    let remaining = 30.0 - (now % 30.0);
    if remaining < 6.0 {
        tokio::time::sleep(Duration::from_secs_f64(remaining + 0.5)).await;
    }
}

// ─────────────────────────── 小工具 ───────────────────────────

fn now_ts() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|value| value.as_secs() as i64)
        .unwrap_or(0)
}

fn now_ts_u64() -> u64 {
    now_ts().max(0) as u64
}

fn url_path(url: &str) -> String {
    let without_query = url.split(['?', '#']).next().unwrap_or("");
    let path = without_query
        .split("://")
        .nth(1)
        .and_then(|rest| rest.find('/').map(|index| &rest[index..]))
        .unwrap_or("/");
    let trimmed = path.trim_end_matches('/');
    if trimmed.is_empty() {
        "/".to_string()
    } else {
        trimmed.to_ascii_lowercase()
    }
}

fn url_host(url: &str) -> String {
    url.split("://")
        .nth(1)
        .and_then(|rest| rest.split('/').next())
        .unwrap_or("")
        .split(':')
        .next()
        .unwrap_or("")
        .to_ascii_lowercase()
}

fn trusted_url(value: &str, base: &str) -> Result<String, RefreshError> {
    let target = auth::absolute_url(value, base);
    let parsed = target
        .split("://")
        .collect::<Vec<_>>();
    if parsed.len() != 2 || parsed[0] != "https" {
        return Err(err("untrusted_auth_url", "response"));
    }
    let rest = parsed[1];
    if rest.contains('@') {
        return Err(err("untrusted_auth_url", "response"));
    }
    let host = rest.split('/').next().unwrap_or("");
    if !TRUSTED_HOSTS.contains(&host) {
        return Err(err("untrusted_auth_url", "response"));
    }
    Ok(target)
}

fn jwt_claims(token: &str) -> Option<Value> {
    let payload = token.split('.').nth(1)?;
    let bytes = base64url_decode(payload).ok()?;
    serde_json::from_slice(&bytes).ok()
}

fn token_expired(token: &str) -> bool {
    let claims = match jwt_claims(token) {
        Some(value) => value,
        None => return false,
    };
    match claims.get("exp").and_then(Value::as_f64) {
        Some(exp) => (now_ts() as f64) >= exp,
        None => false,
    }
}

fn base64url_decode(text: &str) -> Result<Vec<u8>, ()> {
    use base64::Engine;
    let trimmed = text.trim_end_matches('=');
    base64::engine::general_purpose::URL_SAFE_NO_PAD
        .decode(trimmed)
        .map_err(|_| ())
}

fn snippet(body: &str) -> String {
    body.chars().take(300).collect()
}

/// 供 CLI 打印的请求计划（dry-run 不联网）。
pub fn plan_lines(cfg: &RefreshConfig) -> Vec<String> {
    vec![
        format!("快路径    : GET {}/api/auth/session（Cookie {} 条）", CHAT_BASE, cfg.cookies.len()),
        "重登      : warmup → signin → authorize → password/email_otp/mfa/workspace → session".to_string(),
        format!("身份核验  : email={} user_id={} account_id={}", cfg.email, if cfg.user_id.is_empty() { "-" } else { &cfg.user_id }, if cfg.account_id.is_empty() { "-" } else { &cfg.account_id }),
    ]
}

/// 供 Python 契约测试使用的最小成功结果构造器。
pub fn success_json(outcome: &RefreshOutcome) -> Value {
    json!({
        "ok": true,
        "status": "live",
        "access_token": outcome.access_token,
        "session": outcome.session,
        "cookies": outcome.cookies,
        "session_reused": outcome.session_reused,
        "methods": outcome.methods,
        "device_id": outcome.device_id,
    })
}

/// 让上层能把 `anyhow::Error` 里的 `RefreshError` 取出来。
pub fn error_payload(error: &anyhow::Error) -> Option<Value> {
    error
        .downcast_ref::<RefreshError>()
        .map(|value| value.to_json())
        .or_else(|| {
            error
                .chain()
                .find_map(|item| item.downcast_ref::<RefreshError>())
                .map(|value| value.to_json())
        })
}


#[cfg(test)]
mod tests {
    use super::*;
    use base64::Engine;

    fn cfg() -> RefreshConfig {
        RefreshConfig {
            email: "user@example.com".into(),
            password: "pw".into(),
            totp_secret: "SECRET".into(),
            ..Default::default()
        }
    }

    fn b64(value: &Value) -> String {
        base64::engine::general_purpose::URL_SAFE_NO_PAD
            .encode(serde_json::to_vec(value).unwrap())
    }

    #[test]
    fn stage_classification_matches_v3() {
        assert_eq!(classify_stage("", "/log-in/password").unwrap(), "password");
        assert_eq!(classify_stage("password", "").unwrap(), "password");
        assert_eq!(classify_stage("", "/email-verification").unwrap(), "email_otp");
        assert_eq!(classify_stage("", "/mfa-challenge/abc").unwrap(), "mfa");
        assert_eq!(classify_stage("workspace", "/workspace").unwrap(), "workspace");
        assert_eq!(classify_stage("", "/about-you").unwrap(), "account_profile_required");
        assert_eq!(classify_stage("", "/create-account").unwrap(), "account_profile_required");
        assert_eq!(classify_stage("", "/api/auth/callback/openai").unwrap(), "callback");
        assert_eq!(classify_stage("", "").unwrap_err().code, "auth_page_unknown");
    }

    #[test]
    fn trusted_url_rejects_non_https_and_foreign_hosts() {
        assert_eq!(
            trusted_url("https://auth.openai.com/log-in", AUTH_BASE).unwrap(),
            "https://auth.openai.com/log-in"
        );
        assert_eq!(
            trusted_url("/workspace", AUTH_BASE).unwrap(),
            "https://auth.openai.com/workspace"
        );
        assert_eq!(trusted_url("http://auth.openai.com/x", AUTH_BASE).unwrap_err().code, "untrusted_auth_url");
        assert_eq!(trusted_url("https://evil.example/x", AUTH_BASE).unwrap_err().code, "untrusted_auth_url");
        assert_eq!(
            trusted_url("https://user:pass@auth.openai.com/x", AUTH_BASE).unwrap_err().code,
            "untrusted_auth_url"
        );
    }

    #[test]
    fn path_and_host_are_normalized() {
        assert_eq!(url_path("https://AUTH.openai.com/Log-In/Password/?x=1"), "/log-in/password");
        assert_eq!(url_path("https://chatgpt.com/"), "/");
        assert_eq!(url_host("https://auth.openai.com:443/x"), "auth.openai.com");
        assert_eq!(url_host("https://chatgpt.com/x"), "chatgpt.com");
    }

    #[test]
    fn continue_url_prefers_top_level_and_keeps_absolute() {
        let payload = json!({"continue_url": "/email-verification", "page": {"url": "/ignored"}});
        assert_eq!(continue_url(&payload), "https://auth.openai.com/email-verification");
        let nested = json!({"page": {"payload": {"url": "https://auth.openai.com/workspace"}}});
        assert_eq!(continue_url(&nested), "https://auth.openai.com/workspace");
        assert_eq!(continue_url(&json!({})), "");
    }

    #[test]
    fn identity_requires_matching_email_and_claims() {
        let claims = json!({
            "https://api.openai.com/profile": {"email": "user@example.com"},
            "https://api.openai.com/auth": {"chatgpt_user_id": "u-1", "chatgpt_account_id": "a-1"},
            "exp": now_ts() + 3600,
        });
        let token = format!("x.{}.y", b64(&claims));
        let info = json!({
            "accessToken": token,
            "user": {"id": "u-1", "email": "user@example.com"},
            "account": {"id": "a-1"},
        });
        let mut config = cfg();
        config.user_id = "u-1".into();
        config.account_id = "a-1".into();
        assert!(verify_identity(&info, "user@example.com", &config).is_ok());

        assert_eq!(
            verify_identity(&info, "other@example.com", &config).unwrap_err().code,
            "identity_mismatch"
        );
        let mut wrong = info.clone();
        wrong["user"]["id"] = json!("u-2");
        assert_eq!(verify_identity(&wrong, "user@example.com", &config).unwrap_err().code, "identity_mismatch");
        let missing = json!({"accessToken": token, "user": {}, "account": {}});
        assert_eq!(
            verify_identity(&missing, "user@example.com", &config).unwrap_err().code,
            "identity_unconfirmed"
        );
    }

    #[test]
    fn expired_access_token_is_detected() {
        let claims = json!({"exp": now_ts() - 10});
        let token = format!("x.{}.y", b64(&claims));
        assert!(token_expired(&token));
        let fresh = format!("x.{}.y", b64(&json!({"exp": now_ts() + 600})));
        assert!(!token_expired(&fresh));
        assert!(!token_expired("not-a-jwt"));
    }

    #[test]
    fn workspace_prefers_expected_account_then_unique() {
        let payload = json!({
            "oai-client-auth-session": {"workspaces": [
                {"id": "w-1", "account_id": "a-1"},
                {"id": "w-2", "account_id": "a-2"},
            ]},
        });
        assert_eq!(workspace_id(&payload, "a-2").unwrap(), "w-2");
        assert_eq!(workspace_id(&payload, "a-9").unwrap_err().code, "workspace_ambiguous");
        let single = json!({"oai-client-auth-session": {"workspaces": [{"id": "w-9"}]}});
        assert_eq!(workspace_id(&single, "").unwrap(), "w-9");
        let empty = json!({});
        assert_eq!(workspace_id(&empty, "").unwrap_err().code, "workspace_missing");
    }

    #[test]
    fn factor_id_reads_payload_then_url() {
        let payload = json!({"page": {"payload": {"factor_id": "f-1"}}});
        assert_eq!(factor_id(&payload, "https://auth.openai.com/mfa-challenge/x"), "f-1");
        let empty = json!({});
        assert_eq!(
            factor_id(&empty, "https://auth.openai.com/mfa-challenge/f-2"),
            "f-2"
        );
        assert_eq!(factor_id(&empty, "https://auth.openai.com/mfa-challenge"), "");
    }

    #[test]
    fn cookie_snapshot_filters_expired_and_foreign() {
        let client = http::Client::build(super::super::DEFAULT_USER_AGENT, None, http::RetryPolicy::default()).unwrap();
        client.add_cookie("keep", "1", "auth.openai.com", "/", true).unwrap();
        client.add_cookie("chat", "2", "chatgpt.com", "/", true).unwrap();
        client.add_cookie("other", "3", "example.com", "/", false).unwrap();
        let names: Vec<String> = filtered_cookies(&client).into_iter().map(|item| item.name).collect();
        assert!(names.contains(&"keep".to_string()));
        assert!(names.contains(&"chat".to_string()));
        assert!(!names.contains(&"other".to_string()));
    }

    #[test]
    fn error_payload_is_compatible_with_python_classification() {
        let error = err("password_rejected", "auth").no_roxy();
        let payload = error.to_json();
        assert_eq!(payload["error"], "password_rejected");
        assert_eq!(payload["error_category"], "auth");
        assert_eq!(payload["roxy_fallback_allowed"], false);
        assert_eq!(payload["retryable"], false);
    }
}
