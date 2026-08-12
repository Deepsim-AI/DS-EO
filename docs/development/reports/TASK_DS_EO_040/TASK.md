# TASK_DS_EO_040 — Run Execution Reliability (N1)

## Summary
Make OpenClaw runs recoverable when execution and control state diverge. Focus on run-state reconciliation and recovery, not observability.

## Priority
P1 — Run Execution Reliability (N1 critical requirement from audit findings)

## Objective
Recover the `runtime=no active run` / `control=active` impossible state and prevent `/abort` and `/new` deadlocks without requiring OpenClaw restart.

## Scope
See CTO_PLAN.md for detailed scope, state model, failure/recovery matrix, acceptance criteria, and file/symbol guidance.

## Gates
- G1 (Planning): Awaiting user approval of CTO_PLAN.md
- G2 (Implementation): Not started
- G3 (Review): Not started  
- G4 (CTO Approval): Not started
- G5 (PM Closure): Not started

## Status
DRAFT — Plan under review
