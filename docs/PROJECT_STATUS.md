# PROJECT_STATUS.md
- ✅ All tasks through TASK_DS_EO_040 have been approved and closed (G5 complete).
- ✅ TASK_DS_EO_045 has been approved and closed (G5 complete).
- 🚀 Current release version: v0.1.3 (v0.1.4 in progress — see CHANGELOG).
- 📋 2026-08-15: Added `docs/TROUBLESHOOTING.md` (context-window & compaction sizing, broken-session recovery). Config fix applied on this host: `contextWindow` corrected to real model limit (128K), `keepRecentTokens` 120K→50K, `reserveTokensFloor` 48K→24K, `timeoutSeconds` 300→600.
- 🔗 Release notes:
  * Minor bug fixes for the CLI interface.
  * Performance improvements to the task scheduler.
  * Updated documentation for deployment steps.

### TASK_DS_EO_040 — Run-State Reconciliation Layer (G5 Complete 2026-08-13)
Added self-contained run-state reconciliation layer: orphaned run detection, structured error classification, and agent-executable recovery protocols. Zero regression risk.

# CHANGELOG.md
## [v0.1.3] - 2026-08-13
- Fixed issue where task IDs were incorrectly formatted.
- Improved stability of the review process under high load.
- Minor UI tweaks to the webchat dashboard.
