---
pre_barrier: true
tokens_at_write: <current_context_tokens>
tool_calls_completed: <count>
last_artifact_saved: <path or NONE>
next_expected_outcome: <description>
---

# Compaction Barrier — TASK_ID_HERE

**Purpose**: Capture session state before a long-running operation so work can be resumed after compaction/abort.

## Write This Before Each Major Phase

```markdown
---
tokens_at_write: 15000
tool_calls_completed: 23
last_artifact_saved: docs/reports/TASK_XXX/CTO_PLAN.md
next_expected_outcome: Implementer receives dispatch with AC-1 through AC-6
---
```

## When the Barrier Is Found on Session Start

If you find a barrier file from a previous session that never got cleaned up:

1. Read `last_artifact_saved` to determine what was last committed
2. Read `next_expected_outcome` to understand where work left off
3. Report to the user: "Previous session was interrupted at [phase]. Last saved artifact: [path]. Resuming with expected outcome: [outcome]."
4. Do NOT assume completion of work described in a barrier — verify independently

## Cleanup Rule

After successful phase completion, delete the barrier file:
```bash
rm templates/compaction_barrier_<TASK_ID>.md
```

---
*Part of TASK_DS_EO_033 fix for compaction reliability and silent blocking.*
