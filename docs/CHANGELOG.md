# CHANGELOG.md
## [v0.1.3] - 2026-08-13
- Fixed issue where task IDs were incorrectly formatted.
- Improved stability of the review process under high load.
- Minor UI tweaks to the webchat dashboard.

## TASK_DS_EO_040: Run-State Reconciliation Layer ✅ CLOSED (G5 Complete 2026-08-13)
- **reconciler.py** — Orphaned run detection via available APIs
- **error_mapper.py** — Structured error classification patterns
- **recovery_protocol.py** — Agent-executable recovery step sequences
- **59 unit tests** across test_reconciler, test_error_mapper, test_recovery_protocol
- Zero regression risk: entirely new code, no modifications to existing paths
