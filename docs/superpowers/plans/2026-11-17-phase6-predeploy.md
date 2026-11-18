# Phase 6 predeployment verification implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Complete the approved predeployment validation and release preparation, keeping production cutover separate.
**Architecture:** Reuse the existing Web/Worker entrypoints, PostgreSQL facts, task gateway and frozen synthetic fixtures; add independent test harnesses and evidence, not a second runtime.
**Tech Stack:** Python, Flask, Waitress 3.0.2, PostgreSQL, Vue; macOS launchd and target Linux compatibility.
**Spec:** docs/architecture/convergence.md sections 11–12; docs/deployment/split-runtime.md; prior ART parallel-a-20261116/runtime/design.md and failure-matrix.json, reconciled against actual later results.

## Global Constraints

- Current isolated branch codex/architecture-task-center; preserve all existing dirty/private files. No production restart/deploy, real remote business, or real credentials in output. Never execute rm -r. Preserve historical evidence.
- ART=/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-predeploy-20261117. OLD=the sibling parallel-a-20261116 directory.
- Root alone schedules and runs PostgreSQL/scale/fault experiments. Children prepare independently runnable, fail-closed candidates, offline tests and precise commands. No DB access until root grants an explicit exclusive slot.
- Production source is read-only initially. Confirmed product defects require a reproducer and proposed minimal scope sent to root, following the user's discussion-before-new-changes rule. Do not weaken expected behavior to pass a test.
- All live acceptance uses isolated test schemas, synthetic actions and loopback-only external-I/O guards, exact owned process identities, bounded waits and truthful exit/cleanup evidence.
- Prior accepted results are reusable with hash/scope attribution. Historical candidate not_run states are not current failure counts. Do not invent a performance threshold or equate single-client reads with capacity.
- Each lane owns its ART subdirectory. Shared code and fixtures are immutable unless the owner explicitly coordinates a new version. Do not edit another lane's file.
- Reports include files/hashes, exact tests/results, unresolved findings, root command and cleanup protocol. All changes need independent cross-review before acceptance. No staging/commit/push in a child.

### Task 1: Residual fault integration candidates
**Owner:** fault lane; exclusive ART/faults. Consume OLD runtime fault candidates, durable fixture, latest independent failure mapping and accepted results. Produce ART/faults/README.md, driver(s), offline tests, coverage.json and report.md.
- [ ] Reconcile all 33 cases into reused accepted, partial, or missing actual evidence.
- [ ] Prepare root-run real-process/PG scenarios for remaining storage, long-stop/fence, configuration/component, scheduler and business-handoff/drain boundaries. Batch compatible scenarios into one reusable harness; keep remote actions synthetic.
- [ ] Prioritize F15/F16, F20–F29, F30/F31 and exact kill-before-claim residual. Inspect baseline tests first and preserve current semantics.
- [ ] Offline-test candidate guards and failure/cleanup paths. Send the first independent executable slice promptly, then continue other slices.
- [ ] Report exact commands and prerequisites; root executes live DB. Do not stop at a design-only report if an executable fixture can be built.

### Task 2: Real entrypoint switch and rollback rehearsal
**Owner:** rehearsal lane; exclusive ART/rehearsal. Consume OLD/runtime/f33-rehearsal-options.md, phase6-design/verify_runtime_durable_flow.py and OLD/runtime/http-integration/driver.py. Produce factory/harness, driver, offline tests, README and report.
- [ ] Preserve frozen old fixtures; version new support within this lane instead of rewriting historical files.
- [ ] Run actual web.main combined/Flask and web/Waitress plus worker.main, each with exactly one real install/start/stop; inject only synthetic handler and observation endpoints.
- [ ] Prove combined→split→combined→split transitions, one execution owner, generation/nonce changes, queued and terminal task identity/history, configuration snapshots and resource release; preserve unsuccessful attempts.
- [ ] Cover role restart/crash continuity where compatible with this driver, coordinate fault lane to avoid duplicate harness work.
- [ ] Offline-test guards/cleanup; deliver root executable commands, source proof and cleanup audit. DB remains root-only.

### Task 3: Target compatibility and isolated service-manager acceptance
**Owner:** manager lane; exclusive ART/manager. Consume actual deploy templates and role launcher plus tests/tools. Produce isolated synthetic launchd/systemd/target-Python verification fixtures, evidence, readiness checklist and report.
- [ ] Inventory current OS/architecture and supported isolated execution options without reading secrets or changing real services.
- [ ] Exercise actual available service manager using unique disposable synthetic labels and harmless loopback-only child programs, exact identity and cleanup. Never touch an existing production label/unit; do not use privileged containers or alter system settings.
- [ ] Verify independent role lifecycle, automatic restart, maintenance disable/stop and timeout reporting. Template parsing alone is not live manager evidence.
- [ ] Verify locked dependencies on an available isolated ARM64 Linux environment if possible; no production host deployment. If unavailable, report exact missing capability rather than inventing success.
- [ ] Audit release/runbook prerequisites and distinguish predeployment compatibility from postdeployment business acceptance. Send runnable DB-dependent manager fixture to root if needed.

### Task 4: Mixed workload capacity, integration and release evidence
**Owner:** root; exclusive ART/scale and final reports/docs. Consume existing 300k/500k verified datasets; preserve original raw data and manifests.
- [ ] Freeze source/environment and verified dataset facts; build paired old combined versus new split synthetic mixed read/submit/execute scenarios and record actual server+role differences.
- [ ] Measure both scales for main list reads plus active task throughput/wait/fairness, resource/pool peaks, sustained behavior and shutdown; no unapproved target changes.
- [ ] Run children's reviewed live candidates serially; distribute independent cross-reviews while other preparation proceeds. Track each case with proof scope and remaining gaps.
- [ ] Run only necessary final regressions for actual changed product surfaces; reuse unchanged-source evidence accurately. Record a complete matrix and deployment go/no-go.
- [ ] Prepare exact release manifest, runbook, backup/rollback prerequisites, reviewed delivery scope. Production cutover remains separate. Do not include unrelated dirty/private files in any delivery.
