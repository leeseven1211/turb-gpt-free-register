# 2FA Authentication Context Auto-Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify registration, standalone 2FA setup, and account-completion 2FA around `protocol`/`browser` execution modes while automatically selecting how to obtain the authenticated context and preserving the existing `protocol_direct` fast path internally.

**Architecture:** Add a small, pure 2FA mode normalizer/planner that distinguishes the public 2FA executor (`protocol`, `browser`) from the authentication-context source (`existing_at`, `protocol_reauth`, `browser_session`). Treat the legacy `protocol_direct` value as a backward-compatible alias for automatic protocol-first behavior. Account completion will use protocol directly when possible, protocol reauthentication when needed, and Roxy browser fallback when protocol cannot establish a usable context; combinations that require browser password setup will use the browser session to obtain the fresh AT and then protocol for 2FA.

**Tech Stack:** Python 3.12, `unittest`, existing `BrowserSession` protocol client, Roxy Selenium adapter, PostgreSQL-backed task events, existing WebUI config editor and JavaScript choices.

**Spec:** `docs/superpowers/specs/2026-09-02-registration-auth-compatibility-design.md` and the approved automatic-context design from the current conversation.

## Global Constraints

- Keep Roxy as the stable browser mainline and final browser fallback.
- Keep Protocol as a replaceable stage adapter; never log passwords, OTPs, TOTP secrets, ATs, cookies, callback URLs, or raw provider responses.
- `protocol_direct` remains supported for old configuration and internal fast-path execution; it must no longer be passed to the registration-only `TWOFA_DRIVER` validator.
- Protocol 2FA requires an AT that is both valid and recent enough for MFA enrollment; a successful ordinary live check alone is not sufficient evidence.
- Password and 2FA steps remain serial and checkpointed; no account re-registration or duplicate non-idempotent submission is introduced.
- Tests must use fake sessions/drivers and an independent PostgreSQL test database; never use the production schema.

### Task 1: Add the Pure 2FA Mode and Context Planner

**Files:**
- Create: `core/twofa_flow.py`
- Modify: `config/twofa.py:19-38`
- Modify: `config/account.py:17-27,53-73,88-105`
- Test: `tests/test_twofa_flow.py`
- Test: `tests/test_config_defaults.py`

**Interfaces:**
- Produces `normalize_twofa_mode(value: str | None, default: str = "auto") -> str` returning only `auto`, `protocol`, or `browser`, mapping `protocol_direct` to `auto`, `api/http` to `protocol`, and `roxy/roxybrowser` to `browser`.
- Produces `canonical_twofa_executor(mode: str | None) -> str` returning only `protocol` or `browser`; `auto` is protocol-first.
- Produces `plan_twofa_context(mode: str | None, *, has_access_token: bool, browser_session_required: bool) -> TwofaContextPlan` with `executor`, `auth_source`, and `direct_preferred` fields.
- `config.twofa.get_twofa_driver()` must continue returning the canonical executor for existing callers, so legacy `protocol_direct` and new `auto` resolve to `protocol`.
- `config.twofa.get_twofa_mode()` must expose the normalized configured mode for registration snapshots and account workflows.

- [ ] **Step 1: Write the failing planner and config tests**

```python
class TwofaFlowTests(unittest.TestCase):
    def test_protocol_direct_is_auto_protocol_fast_path(self):
        mode = normalize_twofa_mode("protocol_direct")
        plan = plan_twofa_context(mode, has_access_token=True, browser_session_required=False)
        self.assertEqual("auto", mode)
        self.assertEqual("protocol", plan.executor)
        self.assertEqual("existing_at", plan.auth_source)
        self.assertTrue(plan.direct_preferred)

    def test_protocol_without_at_prefers_protocol_reauthentication(self):
        plan = plan_twofa_context("protocol", has_access_token=False, browser_session_required=False)
        self.assertEqual("protocol", plan.executor)
        self.assertEqual("protocol_reauth", plan.auth_source)

    def test_protocol_with_password_setup_uses_browser_session_for_context(self):
        plan = plan_twofa_context("auto", has_access_token=True, browser_session_required=True)
        self.assertEqual("protocol", plan.executor)
        self.assertEqual("browser_session", plan.auth_source)
        self.assertFalse(plan.direct_preferred)

    def test_browser_mode_never_selects_protocol_executor(self):
        plan = plan_twofa_context("browser", has_access_token=True, browser_session_required=False)
        self.assertEqual("browser", plan.executor)
        self.assertEqual("browser_session", plan.auth_source)

    def test_legacy_direct_config_is_accepted_by_twofa_driver(self):
        self.assertEqual("protocol", twofa_config.get_twofa_driver("protocol_direct"))
        self.assertEqual("auto", twofa_config.get_twofa_mode("protocol_direct"))
```

- [ ] **Step 2: Run the focused tests to verify the expected failure**

Run: `PYTHON_DOTENV_DISABLED=1 /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_twofa_flow tests.test_config_defaults -v`

Expected: FAIL because `core.twofa_flow` and the normalized mode API do not exist yet.

- [ ] **Step 3: Implement the minimal planner and normalization API**

```python
@dataclass(frozen=True)
class TwofaContextPlan:
    mode: str
    executor: str
    auth_source: str
    direct_preferred: bool

def normalize_twofa_mode(value=None, default="auto"):
    raw = str(default if value is None else value or "").strip().lower() or default
    return MODE_ALIASES.get(raw, raw) if raw in VALID_MODES | set(MODE_ALIASES) else default

def canonical_twofa_executor(mode=None):
    return "browser" if normalize_twofa_mode(mode) == "browser" else "protocol"

def plan_twofa_context(mode=None, *, has_access_token, browser_session_required):
    normalized = normalize_twofa_mode(mode)
    if normalized == "browser":
        return TwofaContextPlan(normalized, "browser", "browser_session", False)
    if browser_session_required:
        return TwofaContextPlan(normalized, "protocol", "browser_session", False)
    if has_access_token:
        return TwofaContextPlan(normalized, "protocol", "existing_at", True)
    return TwofaContextPlan(normalized, "protocol", "protocol_reauth", False)
```

Update `config/twofa.py` so `TWOFA_DRIVER` defaults to `auto`, `get_twofa_mode()` returns the normalized mode, and `get_twofa_driver()` returns the canonical executor. Update `config/account.py` so `ACCOUNT_2FA_DRIVER` defaults to `auto` and `completion_settings()` exposes the normalized mode.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `PYTHON_DOTENV_DISABLED=1 /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_twofa_flow tests.test_config_defaults -v`

Expected: PASS.

- [ ] **Step 5: Commit the planner and config contract**

```bash
git add core/twofa_flow.py config/twofa.py config/account.py tests/test_twofa_flow.py tests/test_config_defaults.py
git commit -m "feat: define automatic twofa context selection"
```

### Task 2: Make Account 2FA Automatically Acquire a Protocol Context

**Files:**
- Modify: `core/codex_retry_service.py:75-190,408-470,513-596,827-971`
- Test: `tests/test_account_twofa_direct.py`
- Test: `tests/test_auth_completion_matrix.py`

**Interfaces:**
- `_run_protocol_direct_twofa()` remains an internal compatibility entry point, but accepts a missing/stale saved AT by entering the existing protocol email reauthentication flow.
- `run_twofa_worker()` uses normalized mode and the context planner. Pure `auto`/`protocol` 2FA attempts protocol first; pure `browser` uses Roxy UI; password-containing plans force browser session acquisition but keep protocol as the 2FA executor.
- `_build_roxy_account_setup()` receives only canonical `protocol` or `browser`, never `protocol_direct` or `auto`.

- [ ] **Step 1: Add failing regression tests for no-AT protocol reauth and mixed password/2FA mode**

```python
def test_protocol_twofa_without_saved_at_enters_protocol_reauth(self):
    result = self._run_worker(
        account={"id": 9, "email": "a@example.com", "access_token": "", "totp_secret": "", "extra_json": "{}"},
        fallback_enabled=True,
    )[0]
    self.assertTrue(result["ok"])
    self.assertEqual("protocol_reauth", result["twofa_driver"])
    self.assertEqual("protocol_reauth", result["auth_source"])

def test_auto_password_and_twofa_maps_to_protocol_inside_browser_session(self):
    result = self._run_worker(
        account={"id": 9, "email": "a@example.com", "access_token": "saved", "totp_secret": "", "extra_json": "{}"},
        fallback_enabled=True,
        existing_action=Mock(),
        steps={"password", "twofa"},
    )[0]
    self.assertTrue(result["ok"])

def test_legacy_protocol_direct_no_longer_reaches_registration_validator(self):
    setup = build_account_setup_for_test(mode="protocol_direct", steps={"password", "twofa"})
    self.assertEqual("protocol", setup.twofa_driver)
```

- [ ] **Step 2: Run the focused regression tests to verify they fail for the old behavior**

Run: `PYTHON_DOTENV_DISABLED=1 /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_account_twofa_direct tests.test_auth_completion_matrix -v`

Expected: the no-AT case raises `协议直开 2FA 需要账号已有 access_token`, and the mixed mode reaches `ValueError: TWOFA_DRIVER 只支持 protocol 或 browser`.

- [ ] **Step 3: Implement the smallest account-flow change**

1. Normalize `selected_twofa_driver` into a mode before validation.
2. For `requested_steps == {"twofa"}` and protocol-first modes, call the protocol 2FA path.
3. In `_run_protocol_direct_twofa()`, when no saved AT exists, call `setup_2fa()` directly; when an existing AT receives `TwofaEnrollmentAuthRequired`, keep the existing `setup_2fa()` reauthentication path. Persist the new AT through the existing callback and report `auth_source=protocol_reauth`.
4. When protocol fails and browser fallback is enabled, pass canonical `browser` to `_build_roxy_account_setup()`.
5. When `password` is included, map `auto`/`protocol`/legacy direct to canonical `protocol` for the post-password 2FA executor; do not call `get_twofa_driver("protocol_direct")`.
6. Add safe task details `twofa_driver`, `auth_source`, and `browser_opened` without credentials.

- [ ] **Step 4: Run the focused regression tests to verify they pass**

Run: `PYTHON_DOTENV_DISABLED=1 /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_account_twofa_direct tests.test_auth_completion_matrix -v`

Expected: PASS, including the previous `password + twofa + protocol_direct` failure case.

- [ ] **Step 5: Commit the account-flow change**

```bash
git add core/codex_retry_service.py tests/test_account_twofa_direct.py tests/test_auth_completion_matrix.py
git commit -m "fix: auto select account twofa auth context"
```

### Task 3: Apply the Same Mode Contract to Registration and Refresh Boundaries

**Files:**
- Modify: `core/registration_service.py:44-68`
- Modify: `core/registration/roxy.py:4607-4635`
- Modify: `core/registration/protocol.py:427-441`
- Modify: `core/registration/browser_use.py:2009-2024`
- Modify: `core/cloakbrowser_registration.py:125-150`
- Modify: `core/live_check_service.py:86-108,299-325,463-525`
- Test: `tests/test_registration_twofa_auto.py`
- Test: `tests/test_protocol_refresh_selection.py`

**Interfaces:**
- Registration snapshots store normalized mode (`auto`, `protocol`, or `browser`) instead of leaking the legacy direct alias.
- Roxy registration treats `auto` as protocol-first with its existing browser fallback; explicit `browser` remains UI-only.
- Protocol/Browser Use registration accept `auto` as their existing supported protocol behavior and continue to reject unsupported explicit browser behavior where no browser adapter exists.
- Explicit AT refresh keeps its existing `legacy`/`protocol_v2` driver contract; 2FA auto selection may use protocol reauthentication as a context source without silently changing the independent refresh task configuration.

- [ ] **Step 1: Add failing registration and refresh contract tests**

```python
def test_registration_snapshot_normalizes_legacy_twofa_mode(self):
    with patch.dict(os.environ, {"TWOFA_DRIVER": "protocol_direct"}, clear=False):
        snapshot = registration_config_snapshot()
    self.assertEqual("auto", snapshot["twofa_driver"])

def test_roxy_registration_auto_uses_protocol_then_existing_browser_fallback(self):
    self.assertEqual("protocol", canonical_twofa_executor("auto"))

def test_protocol_refresh_is_a_context_source_not_a_new_twofa_driver(self):
    plan = plan_twofa_context("auto", has_access_token=False, browser_session_required=False)
    self.assertEqual("protocol_reauth", plan.auth_source)
    self.assertEqual("protocol", plan.executor)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHON_DOTENV_DISABLED=1 /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_registration_twofa_auto tests.test_protocol_refresh_selection -v`

Expected: FAIL because registration snapshots retain the raw alias and the new automatic mode contract is not wired into registration.

- [ ] **Step 3: Implement registration boundary normalization**

Use `get_twofa_mode()` for snapshots and `canonical_twofa_executor()` at each registration 2FA call. Preserve the existing Roxy `setup_protocol_2fa_with_browser_fallback()` behavior and existing Protocol/Browser Use capability limits. Do not route ordinary live checks through refresh or send OTP as a side effect of a non-refresh operation.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `PYTHON_DOTENV_DISABLED=1 /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_registration_twofa_auto tests.test_protocol_refresh_selection -v`

Expected: PASS.

- [ ] **Step 5: Commit the registration boundary change**

```bash
git add core/registration_service.py core/registration/roxy.py core/registration/protocol.py core/registration/browser_use.py core/cloakbrowser_registration.py core/live_check_service.py tests/test_registration_twofa_auto.py tests/test_protocol_refresh_selection.py
git commit -m "refactor: normalize twofa mode across entrypoints"
```

### Task 4: Update Configuration UI, Documentation, and Compatibility Notes

**Files:**
- Modify: `webui/config_editor.py:161-170`
- Modify: `webui/static/js/modern/config.js:683-695`
- Modify: `webui/static/js/legacy/config.js:34-43`
- Modify: `.env.example:26,134`
- Modify: `README.md` 2FA/account-completion configuration sections
- Modify: `docs/registration-auth-support-matrix.md` sections 2, 4, and 7
- Test: `tests/test_config_defaults.py`

**Interfaces:**
- New UI choices for registration and account completion are `auto`, `protocol`, and `browser` where the entrypoint supports all three; unsupported existing choices remain unsupported and are explained.
- `auto` help text explains: prefer existing usable AT, then protocol reauthentication, then browser session/fallback; it does not expose `protocol_direct` as a separate user decision.
- Legacy `protocol_direct` remains accepted from `.env` and old task snapshots but is displayed/projected as automatic protocol-first behavior.

- [ ] **Step 1: Add failing UI/config assertions**

```python
def test_twofa_ui_exposes_auto_protocol_browser_and_explains_context_selection(self):
    fields = {field["key"]: field for field in config_editor.CONFIG_FIELDS}
    self.assertIn("自动选择", fields["ACCOUNT_2FA_DRIVER"]["help"])
    self.assertNotIn("protocol_direct=", fields["ACCOUNT_2FA_DRIVER"]["help"])
```

- [ ] **Step 2: Run the UI/config test to verify it fails**

Run: `PYTHON_DOTENV_DISABLED=1 /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_config_defaults -v`

Expected: FAIL because the current help text and choices still expose `protocol_direct`.

- [ ] **Step 3: Update UI, example config, README, and support matrix**

Replace public `protocol_direct` wording with the automatic context description. Keep a compatibility note in the support matrix showing that old values are normalized and never passed to the registration-only validator.

- [ ] **Step 4: Run the UI/config test to verify it passes**

Run: `PYTHON_DOTENV_DISABLED=1 /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_config_defaults -v`

Expected: PASS.

- [ ] **Step 5: Commit the UI and documentation change**

```bash
git add webui/config_editor.py webui/static/js/modern/config.js webui/static/js/legacy/config.js .env.example README.md docs/registration-auth-support-matrix.md tests/test_config_defaults.py
git commit -m "docs: expose automatic twofa context selection"
```

### Task 5: Full Verification and Handoff

**Files:**
- Test: all `tests/`

**Interfaces:**
- No new external service or database migration is allowed for this change.
- Final result must retain unrelated dirty changes in the main worktree and report that they were not included.

- [ ] **Step 1: Run focused 2FA and authentication tests**

Run: `PYTHON_DOTENV_DISABLED=1 ACCOUNT_2FA_DRIVER=auto DATABASE_URL="postgresql://turb:turb_local_dev@127.0.0.1:55432/turb_dev" /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest tests.test_twofa_flow tests.test_account_twofa_direct tests.test_auth_completion_matrix tests.test_registration_twofa_auto tests.test_protocol_refresh_selection tests.test_roxy_auth_challenge_flow tests.test_protocol_v2_liveness -q`

Expected: PASS with no production schema access.

- [ ] **Step 2: Run the complete suite and static checks**

Run: `PYTHON_DOTENV_DISABLED=1 ACCOUNT_2FA_DRIVER=auto DATABASE_URL="postgresql://turb:turb_local_dev@127.0.0.1:55432/turb_dev" /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m unittest discover -s tests -q`

Run: `git diff --check && /Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python -m compileall -q core tests`

Expected: all tests pass; no whitespace or compile errors.

- [ ] **Step 3: Verify test database isolation**

Run: `docker exec shared-postgres psql -U turb -d turb_dev -Atc "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'test_%' ORDER BY nspname"`

Expected: no leftover test schemas after the suite.

- [ ] **Step 4: Review the final diff and branch state**

Run: `git status --short --branch && git log --oneline --decorate -8 && git diff --stat dd5221d...HEAD`

Confirm the feature branch is clean and changes are limited to automatic 2FA context selection, account-flow compatibility, UI/docs, and tests.

- [ ] **Step 5: Commit any final verification-only adjustments and report**

Report that real OpenAI/Roxy/email E2E was not run unless an explicitly authorized test account is provided; unit/integration tests use fake sessions and the independent test database.
