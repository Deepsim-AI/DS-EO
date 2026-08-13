---
produced_by: ollama/qwen3.6:35b
session_id: PLACEHOLDER_SESSION
produced_at: 2026-08-10T14:00:00-07:00
role: CTO
task_id: TASK_DS_EO_033
gate: G1
---

# CTO Plan — TASK_DS_EO_033: Fix Compaction Reliability and Post-Abort State Corruption

## Problem Statement

A long-running CTO/Implementer/Reviewer session must **either compact successfully or recover cleanly**. It must never remain silently `livenessState=blocked` because a 120-second compaction timeout occurred.

Prior investigation (TASK_DS_EO_033 = TASK_20260808_033) established two distinct failure modes:
- **Mode #1**: Large accumulated context triggers compaction, summarization LLM call takes too long on CPU-only hardware, times out at 120s → session blocked
- **Mode #2**: Post-abort state corruption — orphaned session artifacts from interrupted runs cause `serializeConversation()` to produce malformed output, hanging subsequent compaction attempts even when context is only at 28%

Both modes leave sessions in a silent `livenessState=blocked` state with no recovery path visible to the user.

## Prior Work Status

The following config changes were partially applied during the original investigation (TASK_20260808_033):
- `compaction.timeoutSeconds`: 120 → 300 (band-aid, doesn't fix Mode #2)
- `reserveTokensFloor`: 80000 → 48000 (extends effective window before compaction triggers)

**Not yet done:**
- Reduce `keepRecentTokens` to trigger compaction earlier with smaller transcripts
- Fix post-abort state corruption at runtime level
- Prevent silent blocking — ensure agents always get a visible recovery path
- Unload idle model pressure (done: removed qwen3.6:27b, gpt-oss:20b, laguna-xs-2.1, ornith:35b)

**This task does NOT include:** Broad performance tuning, architecture changes to the compaction engine itself, or upstream OpenClaw fixes. This task is about **config-driven mitigations and agent-side recovery patterns** that work within current OpenClaw constraints.

## Architecture Decision

### Strategy: Preempt + Isolate + Recover

Since we cannot change the compaction timeout at runtime (it's hardcoded per-config), we must:
1. **Preempt**: Compact earlier with smaller context windows so the 300s timeout is never exceeded
2. **Isolate**: Prevent post-abort corruption from contaminating subsequent compaction attempts
3. **Recover**: Provide visible, non-silent recovery paths when compaction fails

### Why Not Just Raise the Timeout Further?

The investigation confirmed that for ~182K+ token transcripts on CPU-only hardware, even 5 minutes isn't enough. The summarization LLM must process the full context through a large model — this scales with transcript size. Raising timeout is purely additive cost with diminishing returns. **Preemptive compaction at smaller window sizes is the correct lever.**

## Implementation Plan

### Phase 1: Config Hardening (Immediate)
Apply config changes that reduce the transcript size entering compaction to a manageable threshold for CPU hardware.

| Change | Before | After | Rationale |
|--------|--------|-------|-----------|
| `keepRecentTokens` | 200000 | **120000** (~45% of window) | Compact at ~80K tokens instead of ~182K — 2x smaller input, ~4-5x faster summary |
| `maxConcurrent` | 4 | **2** | Prevent model contention during compaction |
| `subagents.maxConcurrent` | 8 | **4** | Reduce total loaded models at once |

### Phase 2: Agent-Side Recovery Protocols (Protocol Update)
Update DS-EO protocols to handle compaction failures gracefully without session death.

#### Protocol Change: Compaction Failure Handling in AGENTS.md §3

Add to each agent's responsibilities:

> **Compaction Awareness**: If a session reports `livenessState=blocked` or "Context overflow: prompt too large", the agent must NOT attempt further tool calls. Instead:
> 1. Acknowledge the blocked state to the user
> 2. Document what work was completed before the block
> 3. Request explicit `/compact` or `/reset` from the user
> 4. When the user confirms, produce artifacts in the task directory BEFORE closing the session (if possible)

This prevents agents from spinning endlessly on a blocked session and wasting tokens trying to recover what can't be recovered.

#### Protocol Change: Post-Abort Cleanup Procedure

After any session abort or compaction failure:
1. The agent MUST run `openclaw status` to check for orphaned states
2. If the session is in a bad state, explicitly request user intervention (`/compact` or `/reset`)
3. Document the failure in the task's RECOVERY_LOG.md

### Phase 3: Artifact Creation (Agent-Side)
For each affected agent role, create a template document that captures pre-compaction state so work isn't lost on failure.

#### New Artifact: `COMPACTION_BARRIER.md`

Before any long-running operation (>10 tool-call rounds), the Implementer/CTO writes a barrier file in the task directory containing:
```markdown
---
pre_barrier: true
tokens_at_write: <current_context_tokens>
tool_calls_completed: <count>
last_artifact_saved: <path or NONE>
next_expected_outcome: <description>
---
```

This is checked at session start (if previous barrier exists, work was interrupted) and updated after each major milestone. If the session dies mid-operation, the next agent reads the barrier to resume from where it left off.

### Phase 4: Model Pressure Management (Operational)
Document which models should be loaded/unloaded for different task phases:

| Phase | Loaded Models | Rationale |
|-------|--------------|-----------|
| CTO planning only | qwen3.6:35b + nomic-embed-text | Minimal — CTO does most work |
| CTO + Implementer | qwen3.6:35b + ornith:35b + nomic-embed-text | Two concurrent sessions, one at a time preferred |
| Review phase | qwen3.6:35b + laguna-xs-2.1 + nomic-embed-text | CTO reviews while reviewer works |
| Full automatic mode | qwen3.6:35b + ornith:35b + laguna-xs-2.1 + nomic-embed-text | All three roles, but stagger dispatch (not concurrent) |

**Critical rule**: Never load all 5 models simultaneously. Each unload of a large model frees ~18-22GB that compaction can use.

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| AC-1 | `keepRecentTokens` set to 120000 in config, verified by `openclaw config get` | Config check confirms value |
| AC-2 | No more than 3 large models loaded simultaneously | `curl localhost:11434/api/tags` shows ≤3 models |
| AC-3 | Compaction failure produces visible user notification, not silent block | Gateway logs show error event + TUI lifecycle event on failure |
| AC-4 | Agent protocol updated to handle blocked sessions gracefully | AGENTS.md §3 documents compaction recovery procedure |
| AC-5 | COMPACTION_BARRIER.md template created and available for use by Implementer/CTO | File exists in templates/ or is documented as agent-side artifact pattern |
| AC-6 | Model pressure management documented in a reference table (per Phase 4) | Documented somewhere accessible to agents during task execution |

## Gate G2 Definition

G2: All config changes applied and verified, protocol updates written to appropriate files. No code changes needed — all fixes are configuration + documentation + agent behavior patterns.

## Gate G3 Requirements

For Reviewer to evaluate:
1. Verify config values are actually written (not just in plan)
2. Verify protocol documents reference the new procedures
3. Check that no agent-side artifacts violate Rule 9 (each role writes only its designated files)
4. Assess whether the recovery protocols would prevent silent blocking

## Scope Boundaries (Prohibited)

- ❌ Modifying OpenClaw source code (that's upstream)
- ❌ Changing the compaction engine itself
- ❌ Adding new Ollama models to replace existing ones
- ❌ Hardware changes (GPU, more RAM)
- ❌ General performance tuning not directly addressing compablility

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Compacting at 120K tokens loses earlier context | Agents write COMPACTION_BARRIER artifacts; prior work is captured in task directory before compact |
| Fewer concurrent agents slows workflow | Automatic mode staggers sessions anyway; manual mode benefits from less model contention |
| Protocol changes only help if agents read them | Documented in AGENTS.md §3 (loaded as project context); also stored in templates/ |
| Models must be re-downloaded after unload | Trade-off: ~20GB freed during active work vs. 10-30s reload time between roles |

---
