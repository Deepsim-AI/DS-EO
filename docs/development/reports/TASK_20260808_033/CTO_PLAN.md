---
produced_by: ollama/qwen3.6:35b
session_id: 1d7936cd-d2ac-4de9-8e07-250effb59a26
produced_at: 2026-08-08T19:26:00Z
role: CTO
task_id: TASK_20260808_033
gate: G1
---

# CTO PLAN — TASK_20260808_033: Cross-Role Compaction Timeout Investigation

## Context

Three DS-EO roles (CTO/qwen3.6, Implementer/ornith, Reviewer/laguna-xs) all experienced compaction timeouts during working sessions. This is a shared OpenClaw runtime/session issue, not model-specific.

## Root Cause Analysis (Already Completed — See INVESTIGATION.md)

The investigation found:
1. `agents.defaults.compaction.timeoutSeconds` defaults to 120s but is **not documented as configurable via the compaction config path** in a reliable way for safeguard mode
2. The safeguard model used for compaction inherits from the same Ollama instance, which can be slow under load (especially with large transcript files ~180K+ tokens)
3. `contextWindow=262144` but `reserveTokens=80000` + `reserveTokensFloor=80000` causes compaction at very small actual windows (~182K estimated prompt vs 182K budget) — the floor is too high for this model's practical usable window
4. The Ollama baseUrl (`http://127.0.0.1:11434`) timeout is set to 600s, but compaction runs via embedded run which uses its own timeout chain

## Investigation Report Location

`INVESTIGATION.md` — contains the full code-path analysis and evidence.

## Implementation Plan

### Step 1: Create INVESTIGATION.md (this session)
- Document the common code path across all three roles
- Trace compaction → safeguard → model call → timeout → abort → TUI feedback
- Document Ollama involvement (or lack thereof)

### Step 2: Config Fix — Increase safeguard timeout and adjust reserveTokensFloor
- Add `compaction.timeoutSeconds` override if not already taking effect
- Lower `reserveTokensFloor` from 80000 to a more appropriate value for qwen3.6:35b's 8192 max output
- Ensure compaction safeguard timeout is explicitly set

### Step 3: Test and Verify
- Apply config changes
- Monitor for successful compaction on next overflow event

## Acceptance Criteria

1. INVESTIGATION.md contains complete cross-role code path analysis
2. Config adjustments documented and applied
3. No more unexplained compaction timeouts during normal operation
