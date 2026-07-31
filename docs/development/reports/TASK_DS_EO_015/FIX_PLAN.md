# TASK_DS_EO_015+017 — Rejection Fix Plan

**Produced by**: CTO  
**Context**: Reviewer returned work with 3 findings at Gate G4. All findings confirmed as real gaps. This plan is a focused correction pass — no new features, just incomplete updates from the initial implementation.

---

## Findings to Fix

### F1: `agents/reviewer.md` deny list docs not updated

**Current (line 29)**:
```
- `tools.deny`: `["write", "edit", "apply_patch"]` — no file modification
```

**Required**:
```
- `tools.allow`: `["group:fs", "web_search", "web_fetch", "exec", "process", "write"]` — write REVIEW_REPORT.md; read and inspect for verification
- `tools.deny`: `["edit", "apply_patch"]` — no source code modification
```

Also update:
- Line ~90 Deliverables section: change "Review findings as a session/chat artifact (you cannot write repository files)" to "Produce REVIEW_REPORT.md in your task directory"
- Delivered artifacts table: add `REVIEW_REPORT.md` to file-based deliverables
- Forbid Actions section: update to reflect that writing REVIEW_REPORT.md is now allowed

### F2: Workspace mirror `communication_protocol.md` not synced

The authoritative `protocols/communication_protocol.md` correctly has TASK_STALLED. The workspace mirror at `docs/development/protocols/communication_protocol.md` still has 3 PM_STALLED references:
- Line ~50: `### 3. Task Stalled (PM_STALLED)` → `### 3. Task Stalled (TASK_STALLED)`
- Line ~57: `"type": "PM_STALLED"` → `"type": "TASK_STALLED"`
- Line ~65: `- **Format**: PM_STALLED message type.` → `- **Format**: TASK_STALLED message type.`

### F3: Workspace mirror missing GATE_AUTHORITY_MATRIX.md

`protocols/GATE_AUTHORITY_MATRIX.md` exists in authoritative but not in `docs/development/protocols/`. Copy it.

### F4 (cleanup): Stale .ds-eo-bak file in workspace mirror

`docs/development/protocols/communication_protocol.md.ds-eo-bak` is a leftover backup with old content. Delete it to prevent confusion.

---

## Delegation for Implementer

**Task**: TASK_DS_EO_015+017 (rework / corrections pass)

### Files and Changes Required

| # | File | Action |
|---|------|--------|
| 1 | `agents/reviewer.md` line 29 | Replace deny list with updated values matching config change |
| 2 | `agents/reviewer.md` Deliverables section | Change "you cannot write repository files" to "produce REVIEW_REPORT.md in your task directory" |
| 3 | `agents/reviewer.md` Forbid Actions | Update to allow REVIEW_REPORT.md write, still forbid code modification |
| 4 | `docs/development/protocols/communication_protocol.md` lines ~50,57,65 | Rename PM_STALLED → TASK_STALLED (3 refs) |
| 5 | `docs/development/protocols/GATE_AUTHORITY_MATRIX.md` | Copy from `protocols/GATE_AUTHIVITY_MATRIX.md` (same content) |
| 6 | `docs/development/protocols/communication_protocol.md.ds-eo-bak` | Delete |

### Acceptance Criteria for This Fix Pass

1. No line in `agents/reviewer.md` says write is denied — deny list matches config: `["edit", "apply_patch"]`
2. Reviewer's deliverables explicitly include REVIEW_REPORT.md as a file-based artifact it produces
3. `docs/development/protocols/communication_protocol.md` has zero PM_STALLED references (3 renamed to TASK_STALLED)
4. `docs/development/protocols/GATE_AUTHORITY_MATRIX.md` exists and matches `protocols/GATE_AUTHORITY_MATRIX.md` exactly
5. No `.ds-eo-bak` or other stale backup files remain in the workspace mirror

### Verification After Fix

```bash
# F1: reviewer.md deny check
grep 'tools.deny' agents/reviewer.md  # should show ["edit", "apply_patch"] only

# F2: mirror PM_STALLED count
grep -c 'PM_STALLED' docs/development/protocols/communication_protocol.md  # should be 0

# F3: mirror has GATE_AUTHORITY_MATRIX
test -f docs/development/protocols/GATE_AUTHORITY_MATRIX.md && echo "OK" || echo "MISSING"

# F4: no stale backups
ls docs/development/protocols/*.bak 2>/dev/null | wc -l  # should be 0
```

---

## Gate Re-Submission Process

1. Implementer makes the 6 fixes above
2. Implementer verifies with acceptance criteria checks
3. CTO issues Gate G4 approval (this plan + implementer's verification = sufficient for re-submission)
