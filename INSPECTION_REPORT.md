# DS-EO OpenClaw Test — Inspection & Test Report

**Workspace:** `ds_eo_dsh`
**Date:** 2026-09-27
**Environment:** Python 3.10.12 · pytest 9.1.1 · PyYAML 6.0.2 · Jetson Orin (read-only `~/.openclaw`)
**Scope:** Architecture review, full test-suite execution, failure root-cause analysis. **No code was modified** (per instruction).

---

## 1. Repository Architecture

`ds_eo_dsh` is **DS‑EO (Deepsim Engineering Organization) — OpenClaw Edition**: a portable
"engineering team" framework that wraps an OpenClaw agent host. Three planes:

| Plane | Contents |
|-------|----------|
| **Governance (non-code)** | `AGENTS.md` (role rules), `protocols/` (gates, review, handoff), `templates/`, `config-templates/`, `agents/*.md` prompts, `ds_eo_manifest.yaml` (single source of truth) |
| **Python engine** | Top-level `ds_eo_dsh/` package: `workflow/` (11-state state machine, audit hash-chain, mode selector, failure/stall/escalation), `session_health/` (discover→classify→policy→execute→audit monitor + Phase-7 OpenClaw API), `run_reliability/` (reconciler, recovery protocol, error mapper), `intake/`, `release_manager/`, plus a parallel `dispatcher/` package (registry w/ SHA256 checksums, YAML-driven G0–G4 gate machine, `state_manager`, `session_dispatch/supervisor`, `execution_strategy/` for hardware-aware model concurrency) |
| **Tests** | `tests/` (main pytest suite), `test/execution_strategy/` (self-contained suite), `tests/test_installation_flow.sh` (shell smoke test); CI: `.github/workflows/release.yml` (manual release gate that runs `pytest`) |

---

## 2. Test Results

| Suite | Collected | Passed | Failed | Time |
|-------|:---------:|:------:|:------:|:----:|
| `tests/` (main) | 570 | 568 | **2** | 34.9s |
| `test/execution_strategy/` | 53 | 53 | 0 | 5.1s |
| `tests/test_installation_flow.sh` | 10 | 10 | 0 | — |
| **Total** | **631** | **629** | **2** | — |

---

## 3. Failure Diagnosis

**Failing tests** (both in `tests/test_session_health.py`):
- `TestExecutorPhase7::test_warn_delivers_notification`
- `TestExecutorPhase7::test_protected_session_warn_only`

**Symptom** — both assert `result.success is True` for the `WARN` lifecycle action and receive:
```
ActionResult(success=False, ..., details='Notification directory could not be written')
```

### Root cause — environment + test-hermeticity interaction (not a product logic bug)

1. `SessionHealthExecutor._execute_warn()` (`ds_eo_dsh/session_health/executor.py:199-246`) writes a JSON
   notification file to a **hard-coded** absolute path:
   `os.path.expanduser("~") + "/.openclaw/notifications/"`.
   - The constructor (`executor.py:84`) exposes **no** `notification_dir` parameter.
   - The fixture `executor_with_mock_api` (`tests/test_session_health.py:852`) mocks the OpenClaw API
     but does **not** redirect the notification directory.
   → The executor always targets the **real** `~`.

2. On **this** host, `~/.openclaw` sits on a **read-only volume**. Direct probe reproduces the error:
   ```
   OSError [Errno 30] Read-only file system: '/home/deepsim/.openclaw/notifications/_selftest.json'
   ```
   (`mkdir` "succeeds" only because the dir already exists; the **file write** is what is blocked.)

3. `_execute_warn` catches the `OSError` and returns `success=False, details="Notification directory could not be
   written"` — exactly the observed failure string.

### Proven environmental (not code)

Re-running the two tests with `HOME` redirected to a **writable** temp directory makes **both pass**, and the
expected JSON artifacts are produced correctly:
```
HOME=/tmp/fakehome-*  →  2 passed in 0.06s
  …/notifications/test-session_2026-09-27T….json
  …/notifications/protected-session-key_2026-09-27T….json
```
The WARN logic works — it simply cannot write to the real read-only `~/.openclaw` under this sandbox.
On a normal writable host (e.g. the GitHub runner), the suite passes.

### Classification

**Test-isolation / portability defect** (non-hermetic test writes to `$HOME`) amplified by a host constraint
(read-only `~/.openclaw`). **No product-code logic fault.**

### Remediation (not applied)

Make the notification target injectable — add a `notification_dir` kwarg to
`SessionHealthExecutor.__init__` (or env `DS_EO_NOTIFICATION_DIR`), defaulting to `~/.openclaw/notifications/`,
and point the two WARN tests (or the mock-API fixture) at `tmp_path`.

---

## 4. Minor (non-failing) Observations

- **Stale protocol reference:** `scripts/deploy_protocols.sh` lists `implementation_protocol.md` in
  `PROTO_FILES`, but that file does not exist in `protocols/`. The script skips it gracefully
  (`✗ Source not found … (skipping)`) so the smoke test still passes — but the reference is stale.
- **Release-gate sensitivity:** `.github/workflows/release.yml` (line 132) runs `pytest` from the repo root.
  On this read-only-`~/.openclaw` host it trips the same 2 WARN failures and **aborts the release**.

---

## 5. Summary

The test estate is healthy: **631 cases, 629 passing**. The **only** two failures
(`test_warn_delivers_notification`, `test_protected_session_warn_only`) trace to `SessionHealthExecutor._execute_warn`
writing to a hard-coded, non-overrideable `~/.openclaw/notifications/` directory that is **read-only on this host**.
This is a **test-hermeticity / portability gap** combined with an environment constraint — **not** a logic fault in
the engine. **No code was modified**, per instruction.
