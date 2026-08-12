---
title: Run Execution Reliability — Run-State/Liveness Desynchronization Deadlock
task_id: TASK_DS_EO_039
created_at: 2026-08-11T17:18:00-07:00
status: OPEN
priority: CRITICAL
---

# User Request

**From user (2026-08-11 17:18 PDT):**

New evidence: the OpenClaw failure is now happening frequently and is more severe than a normal run abort.

Observed sequence:

1. CTO agent is actively working: "Now let me update the code to use this correctly:"
2. `run aborted`
3. UI says: "This response is taking longer than expected. Still waiting for the current run."
4. `no active run` appears.
5. `/new` is refused with: `abort the current run before /new`
6. `/abort` is also refused with the same message.
7. Repeated attempts alternate between `no active run`, `run aborted`, and `abort the current run before /new`.
8. Eventually the TUI remains connected but unusable.
9. Only Ctrl+C and restarting OpenClaw recovers the session.

This indicates a likely run-state/liveness desynchronization: the actual runtime reports no active run, while the TUI/control state continues to believe a run is active. This creates a deadlock where both `/abort` and `/new` are blocked even though there is no actual active run.

Requirements:
- Add this as a concrete failure case to the Run Execution Reliability analysis
- Investigate how the system enters `runtime = no active run` + `TUI/control = active run`
- Determine authoritative source of run state, stale state storage, and recovery paths
- Correlate with previously identified abort/lifecycle race in TASK_DS_EO_032/033
- Investigate token-accounting display issue (tokens 570k/262k (217%))

Do not treat as merely a TUI cosmetic problem. The fact that `/new` and `/abort` are both blocked means it is a control-plane liveness problem.
