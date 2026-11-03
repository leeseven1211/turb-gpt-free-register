# Sentinel / Cloudflare Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development; follow the scoped tasks and preserve all existing worktree changes.

**Goal:** Add SDK maintenance and bounded, opt-in same-session challenge recovery while preserving existing tasks with all new switches off.

**Architecture:** SDK discovery remains an explicit diagnostic tool and never updates the active SDK. A separate sandboxed DOM runtime delegates network I/O to a policy-enforcing Python bridge. Only the local Protocol anonymous login preflight is eligible for automatic recovery. The wreq adapter is retained for explicit diagnostics; protocol-2 registration integration and its dedicated flag have been withdrawn after the reachability audit below.

**Tech Stack:** Python 3.10+, existing StageBudget/cancellation, Node >=20, isolated jsdom dependency.

**Spec:** `docs/superpowers/specs/2026-11-03-sentinel-cloudflare-integration-design.md`

## Global Constraints

- User approved execution of the proposed sequence on 2026-11-03; no further approval is required for these bounded code changes.
- All recovery switches default off. Do not enable runtime configuration, operate real accounts, restart, commit, push or deploy.
- No `rm -r` or `rm -rf`. Preserve unrelated Sub2API/password changes.
- Tests use `/tmp/turb_sub2api_test.py`, which selects `turb_test` and an isolated schema; mock external account requests.
- Cancellation propagates; optional feature errors return the original response. Never replay business mutations, send OTP, change account identity, or clear the global circuit indiscriminately.
- Cache candidates only. Do not activate new SDKs or change version/fingerprint fields in this implementation.

## Task 1: Sentinel candidate resource manager

Files: `core/auth/protocol/sentinel_assets.py`, `tools/diagnostics/check_sentinel_assets.py`, `tests/auth/test_sentinel_assets.py`.

- [x] Test first: official loader parsing, hostile/multiple URLs, content validation, same version changed bytes, stale/corrupt cache, failed fetch preserving good artifact, atomic concurrent access.
- [x] Implement immutable artifact metadata and content-addressed files under a caller-provided cache directory. Strict official redirect policy and bounded download. Static compatibility distinguishes generic/Proto2 and never claims runtime success.
- [x] Add standalone CLI with explicit refresh, safe JSON/text output, and no registration dependency.
- [x] Run targeted tests and review; check `sentinel/sdk.js` and active paths are untouched.

## Task 2: Cloudflare policy and same-session coordinator

Files: `core/network/cloudflare.py`, `tests/network/test_cloudflare_recovery.py`.

Interfaces shared with Task 3: `solve_challenge(transport, response, *, url, headers, profile, budget, runtime_factory=None) -> SolveResult`; runtime factory called with `payload, bridge, budget`, returning a boolean indicating completion. `bridge(request_dict) -> response_dict` handles all I/O. Default runtime lazy-imports `core.network.cloudflare_runtime.run_runtime`.

Payload: `url`, `html`, `userAgent`, `browserIdentity`, `cookies` (non-HttpOnly only), `waitMs`. Bridge requests: `method`, `url`, `headers`, `body`, `kind`; responses: `status`, `url`, `headers` (safe subset), `body` (base64), `cookies` (non-HttpOnly current origin only).

- [x] Test first: confirmed versus ordinary 403/429, exact anonymous URL, protected methods/endpoints, request/response/time caps, redirects, cancellation, clearance versus verified content.
- [x] Implement challenge classification and strict bridge allowlist (original login page for verification only; `/cdn-cgi/challenge-platform/` on chatgpt.com or challenges.cloudflare.com for challenge I/O). No generated Authorization/Cookie/Host headers or inherited cross-origin authentication.
- [x] Preserve original transport, cookies and proxy; use no automatic redirects or transport retry. Report safe status/reason/counts and original response on failed verification.
- [x] Runtime unavailable/unsupported returns bounded failure without changing existing business response.

## Task 3: Sandboxed DOM experiment

Files: `core/network/cloudflare_runtime.py`, `sentinel/cloudflare/*`, `tests/network/test_cloudflare_runtime.py`.

- [x] Test first with locally authored fixtures: event bridge, parent/iframe exchange, no Node direct network, hard deadline/cancellation, malformed or oversized messages, sandbox unavailable.
- [x] Implement Task 2 runtime factory contract using one-shot subprocesses; use inherited-environment allowlist and OS isolation (macOS sandbox-exec; unavailable platforms report unsupported).
- [x] Vendor only the required MIT-licensed DOM reference with attribution or author a focused equivalent. Lock jsdom, maintain separate dependencies, and do not change existing Sentinel runner.
- [x] Run real sandboxed fixture smoke tests, check clean child-process teardown and no direct network/file access.

## Task 4: Default-off local preflight hook and diagnostic transports

Files: `config/openai_protocol.py`, `core/auth/protocol/openai_auth.py`, `core/network/cloudflare_adapters.py`, config schema/docs and focused regression tests.

- [x] Record baseline existing auth/Proto2 tests before integration.
- [x] Add `OPENAI_CF_PREFLIGHT_ENABLED=False`; exact anonymous GET login page only. Lazy import solver only if enabled and actual challenge exists. One attempt per session; no normal-response overhead or replay; bounded timeout shared with recovery verification.
- [x] BrowserSession adapter bypasses only this challenge's local circuit through original raw transport, records traffic, and restores original failure/cooldown on failure. No unrelated circuit is cleared.
- [x] Retain the original wreq transport/cookie store adapter for explicit diagnostics only. The automatic protocol-2 registration hook and its dedicated flag were withdrawn after reachability validation; the registration runtime is restored to its prior implementation.
- [x] Add failure-injection tests proving unavailable runtime, bridge error, cancellation, 429 and nonchallenge responses do not cause extra business submissions; disabled paths retain existing request counts and outcomes.

## Task 5: Final verification and documentation

- [x] Independent review each subsystem for spec compliance and quality; fix findings before completion.
- [x] Run combined new tests, existing auth/registration/transport tests and prior Sub2API/password tests. Run lint and diff whitespace checks. Do not infer online registration benefit from offline tests.
- [x] Document commands, off defaults, platform/dependency support and observed limits. Report implementation/test status separately from enablement and deployment.

## Execution rulings

- No SDK activation: the approved first deliverable is discovery/candidate maintenance; current official bytes equal the active SDK, so activation adds risk without a version benefit.
- Recovery is optional and fail-open to the original result, not to success. Runtime unavailable must not make an otherwise successful task fail.
- Parallel work is limited to disjoint new modules with the above fixed interfaces. Root owns existing config/preflight changes.
- Protocol-2 automatic recovery was withdrawn: its normal warmup is `/api/auth/csrf`, so the previous login-page-only hook had no default-path benefit. Keep its original request sequence intact.

## Follow-up: maintenance panel — 2026-11-03

The user requested a persistent UI entry instead of remembering the diagnostic command.

- [x] Add **配置 → 系统与维护 → 通用配置 → Sentinel 检查** using the existing configuration layout.
- [x] Read local status only when the card is visible; explicitly clicking **检查 Sentinel 更新** starts the download. Show builtin/candidate versions, last check, content comparison and static compatibility.
- [x] Use an independent maintenance worker and cross-process single-flight lease, with fast local reads during download. Keep normal account/registration worker queues untouched.
- [x] Preserve good candidates on failure, suppress raw diagnostic data, and reject client-provided paths/URLs/activation instructions.
- [x] Update only the card after checks, preserving unsaved configuration fields; stop polling on navigation or a hidden page.
- [x] Enforce a hard worker deadline, including stalled DNS; independently review and verify the finished implementation.
- [x] Record focused regressions, browser checks, and any unrelated existing test failures.


## Verification record — 2026-11-03

- Sentinel candidate manager: 48 offline tests, including concurrent spawned processes; no fork warnings. Standalone CLI actually refreshed only official public assets, found version `20260810913b`, SHA256 `49d0284bf3eea8a59ebcad0e6b5dd8a53edd4c72606f15bbf51ebe5610a88efd`, identical to active SDK; static marker reports explicitly retain `runtime_verified=false`.
- CF coordinator: 33 tests and 31 subtests, including real wreq header/cookie representations, verification-time reservation, stream deadline checks and explicit interactive challenge rejection.
- DOM runtime: 15 real macOS sandbox fixture tests. Node direct file/network/process attempts blocked, hard deadline/cancellation reaps child group. Other platforms report unsupported, without an unisolated fallback. V8 heap is capped; there is no independent total native RSS hard limit.
- Independent final CF review: approved spec and quality; 105 scoped tests and 41 subtests passed. Sentinel/adapters/preflight also independently reviewed.
- Review fixes have regression evidence: preserve original 403 cooldown (new429 still observed), safe-only debug views for new challenge bridge traffic, accurate original-wire timing, and cleanup exceptions cannot mask cancellation.
- Ruff, Node syntax and whitespace checks passed. Active SDK, Python/JS Sentinel runners, Proto2 SDK loader and private hook adapter are unchanged.
- Final broad regression: **2533 passed, 1119 subtests passed**, no warnings, 324.61 seconds in pytest (330.282 seconds including isolated launcher). Covers all `tests/auth`, `tests/registration`, `tests/network`, the new password setup suites, and Sub2API client/jobs/monitor/upload/automation/config/API suites. Earlier broad run found one coordinator test while implementation was still in progress; its correction and the final complete rerun are green.
- Runtime configuration remains off. No real-account task, Cloudflare live challenge, service restart, commit, push, deployment or SDK activation occurred. Anonymous real challenge effectiveness remains an operational follow-up; no success-rate claim is made from fixtures.

### Follow-up: protocol-2 reachability audit

- The user challenged whether the existing anonymous-login hook is reachable in normal protocol-2 registration. Adapter support had been verified without establishing business-path usefulness; the earlier completion claim must not be read as evidence of a protocol-2 success-rate improvement.
- Ran the real upstream `AuthFlow.run_register` with a fake lowest-level transport, fixture Sentinel tokens and no-op diagnostic/password side-effect callbacks. All normal flow methods were preserved. The complete successful fixture made 16 simulated HTTP requests, none to the exact login page; the enabled recovery hook was called **0 times**. Default warmup and CSRF acquisition both use `/api/auth/csrf`; login-page strings there are Referer values. An explicit login-page `WARMUP_URL` override produced **1 call** in the control case.
- Streamed redirect requests remain excluded. A few non-streaming fallback reads use server-provided URLs and could match the login page after authentication has progressed; URL/method/stream checks alone do not enforce the promised pre-email phase. This needs a revised scoped design before enablement.
- Read-only local history inspection found no sufficient request-level capture for the bounded recent task sample. The normal service `.env` does not override `WARMUP_URL`; its running process environment was not inspected. No historical request-frequency or live-challenge-effectiveness claim is justified.
- Updated the maintenance guide to recommend leaving the protocol-2 experiment off. This audit changed documentation only; it did not add navigation, expand recovery endpoints, enable configuration, restart the service or operate a real account.

### Follow-up: protocol-2 integration withdrawn

- The user requested removal after the audit. Removed the automatic registration hook, dedicated configuration/schema/env/export entries and the now-unused `recover_wreq_preflight` wrapper. The protocol-2 runtime matches the existing HEAD implementation exactly, including cancellation, diagnostics, stream handling and traffic accounting.
- Retained the local Protocol recovery hook, shared isolated runtime/coordinator, explicit wreq diagnostic transport and Sentinel maintenance panel. The wreq transport remains used by the standalone probe.
- Red/green behavior evidence: before withdrawal, an exact login-page challenge with an enabled context invoked the shared solver once; afterward, the original response and request arguments pass through with zero solver calls, even with a stale caller context. The removed flag is absent from editor metadata and rejected by config validation; the local Protocol flag remains usable.
- Final combined isolated regression: **366 passed, 1458 subtests passed**. Covers protocol-2 registration/transport/diagnostics, existing protocol password/identity reconciliation, CF coordinator/adapters/real sandbox fixtures, local Protocol preflight, config schema/loading/runtime contracts and Sentinel maintenance service/API/UI. Independent review passed with **107 related tests** and byte-for-byte runtime comparison. Ruff and whitespace checks passed.
- No production data/configuration changes, real account actions, service restart, commit, push or deployment occurred.

### Maintenance panel follow-up verification

- Final isolated service/assets/API/UI/route/Sub2API/CloudMail set: **90 passed, 17 subtests passed**. Existing configuration schema/runtime/loading/routes and WebUI runtime regression set: **146 passed, 1406 subtests passed**. Existing frontend configuration navigation/proxy/deployment regressions: **40 passed**.
- Independent review passed. A real diagnostics CLI with an intentionally stalled resolver was killed and reaped in 0.436 seconds under a 0.4-second test deadline; the previous candidate and failure record survived service reconstruction. Production download subprocess budget is 35 seconds. Output-pipe exceptions also terminate/reap before the maintenance lease is released.
- Browser verification used an isolated Flask preview with stub API data: the card appeared in the intended menu, clicking issued the explicit check request, and an unsaved configuration value remained unchanged. The preview server was stopped afterward; no real WebUI was restarted.
- Route contract retains the original 163-route hash. Five exact additions from existing commits and the four current Sub2API/Sentinel additions are explicitly asserted before checking that baseline; no removed or changed route is hidden.
- An earlier exploratory `tests/config` plus dashboard run had **12 failures, 341 passes and 1501 subtest passes** in existing email configuration expectations, dashboard fixture tables/filter assertions and lease validation. Those unrelated areas were not changed for this maintenance button; this record does not claim the full repository test suite is green.
- Ruff, JavaScript syntax and whitespace checks passed. No service restart, real account operation, SDK activation, commit, push or deployment was performed for the panel.
