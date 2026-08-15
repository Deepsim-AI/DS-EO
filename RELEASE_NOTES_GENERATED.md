# Release Notes — v0.9.1

**Release type:** patch
**Previous version:** 0.9.0
**New version:** 0.9.1
**Released by:** DS-EO automated release workflow

## Changes

e8e4295 fix(workflow): initialize NEW_MAJOR/NEW_MINOR before case statement in semver bump
3555180 fix(workflow): fix version-bump step — use base64-encoded Python to avoid heredoc/YAML indentation conflicts
35ee359 fix(workflow): indent heredoc body to fix YAML parse error
cd7f3b8 fix(workflow): re-register with double-quoted "on" trigger
dc19fab temp: remove workflow for GitHub refresh
0cebd58 fix(workflow): use double-quoted "on" for reliable GitHub Actions parsing
d2fb444 fix(workflow): quote 'on' key to fix workflow_dispatch trigger parsing
cea6d45 chore: fix portability test, bump manifest to 0.9.0 (release readiness)
2f77506 doc: update all docs for G0 intake model with TASK_REQUEST.md and LOCK.md
8ec75bd protocol: add G0 intake model with TASK_REQUEST.md and LOCK.md folder locking
1b1e20d [PM] TASK_DS_EO_043 G5 Closure: Execution Strategy Manager Phase A

---

## Changelog Entries (most recent)

## TASK_DS_EO_039: Run-State/Liveness Desynchronization Fix ✅ CLOSED
## TASK_DS_EO_040: Run-State Reconciliation Layer ✅ CLOSED (G5 Complete 2026-08-13)
## [v0.9.1] — 2026-08-14
## [v0.9.0] — 2026-08-11
## [v0.4 — Dispatcher/Workflow Engine Layer] — 2026-08-05
## [v0.5 — Task Intake Manager Layer] — 2026-08-07
## [v0.5.1 — Failure Detection and Recovery Layer] — 2026-08-07
## [v0.6 — Session Health and Lifecycle Management] — 2026-08-08
## [v0.7 — Upstream Bug Reports & Runtime Investigations] — 2026-08-08
## [v0.8 — Session Health Real OpenClaw API Integration] — 2026-08-09
