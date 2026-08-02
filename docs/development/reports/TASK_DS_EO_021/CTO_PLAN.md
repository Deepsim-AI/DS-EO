# CTO Plan — TASK_DS_EO_021

**Task ID**: TASK_DS_EO_021  
**Title**: Phase 2 — Audit Trail Integration  
**Date**: 2026-08-02  
**CTO**: qwen3.6:35b (ollama)  
**Spec Reference**: `docs/development/reports/TASK_DS_EO_019/EXECUTION_MODE_ARCHITECTURE.md` §10

---

## 1. Problem Statement

Phase 1 implemented the core state machine engine but left the audit trail unimplemented — in automatic mode, transitions would leave no traceable record of who decided what and when. Phase 2 closes this gap by producing a schema-compliant audit logging system so that every transition (manual or automatic) is fully reconstructable from records alone.

This task produces:
1. Audit log module `ds_eo_openclaw/workflow/audit_log.py` with full §10 schema compliance
2. Integration of audit entry creation into `state_engine.py`'s `auto_advance()` and manual transition paths
3. Project-level audit index (`docs/reports/AUDIT_INDEX.json`) for cross-task navigation
4. Reconstruction verification test proving full history can be rebuilt from audit data alone

---

## 2. Current-State Analysis

### 2.1 What Exists Now (for this task)

| Component | Location | Notes |
|-----------|----------|-------|
| State engine module | `ds_eo_openclaw/workflow/state_engine.py` | Has `audit_log: List[dict]` field but entries lack full schema fields |
| Audit architecture spec | `EXECUTION_MODE_ARCHITECTURE.md` §10 (§10.2) | Defines 14 required fields per entry, storage format, reconstruction requirements |
| State engine tests | `tests/test_state_engine.py` | No audit-related tests yet |

### 2.2 What Does NOT Exist Yet (to be created)

| Component | New Location | Description |
|-----------|-------------|-------------|
| Audit log module | `ds_eo_openclaw/workflow/audit_log.py` | Full §10 schema: 14 fields, UUID auditId, ISO-8601 timestamps, null-safe scoring |
| Per-task audit storage | `TASK_<id>/AUDIT_LOG.json` | Created at task creation; entries appended per transition |
| Project-level audit index | `docs/reports/AUDIT_INDEX.json` | Flat list with latestState + lastAuditTime per task for cross-task navigation |
| Reconstruction test | `tests/test_audit_log.py` | Verifies 6 scenarios: approved pass, G2 fail, G3 reject, G4 reject, rework loop, blocker |

### 2.3 What Needs to Change (to be modified)

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `state_engine.py` | Modify | `auto_advance()` creates full AuditEntry instead of partial dict; manual transitions also create audit entries |
| `test_state_engine.py` | Add tests | Audit integration tests for auto and manual mode |

---

## 3. Design Analysis

### 3.1 Audit Entry Schema (§10.2)

Every audit entry must contain these 14 fields:

| Field | Type | Description |
|-------|------|-------------|
| `auditId` | string (UUID) | Unique identifier for this entry |
| `taskId` | string | TASK_<YYYYMMDD>_<NNN> |
| `transitionKey` | string | T0–T8 transition key from architecture (§3.4) |
| `fromState` | string | State ID before transition (e.g., "TASK_OPEN") |
| `toState` | string | State ID after transition |
| `gatePassed` | string or null | Gate name if applicable (G1, G2, G3, G4), null otherwise |
| `gateStatus` | string | Decision at the gate: APPROVED, REJECTED, CHANGES_REQD; always present, never null |
| `agentId` | string | ID of the agent that triggered this transition |
| `executionMode` | string | "manual" or "automatic" |
| `triggeredBy` | string | Entity name (CTO, PM, Reviewer, User) |
| `timestamp` | string | ISO-8601 timestamp (UTC) |
| `details` | object | Transition-specific context (per §10.2 Table) |
| `verifiedArtifacts` | array[string] | Artifacts verified at transition time |
| `reconstructionHash` | string | SHA-256 of all preceding entries for integrity chain |

### 3.2 Storage Strategy (Per-Architecture Recommendation)

**Recommended: Per-task audit log + project-level index**

```
docs/development/reports/TASK_<id>/
├── CTO_PLAN.md
├── AUDIT_LOG.json          ← Appended per transition
└── ...

docs/reports/
└── AUDIT_INDEX.json        ← Cross-task flat list: { taskId, latestState, lastAuditTime }
```

Rationale: Per-task keeps audit data co-located with task artifacts for easy navigation. Project-level index enables cross-task scanning without reading every task's audit log.

### 3.3 Integration Points

| Integration | How It Works |
|-------------|--------------|
| `auto_advance()` in state engine | On every successful transition, creates full AuditEntry with gateStatus + verifiedArtifacts; appends to task AUDIT_LOG.json |
| Manual mode transitions | PM or CTO calls audit module's `create_entry()` function for any handoff that crosses a gate boundary |
| State engine detection changes | When detect_state() result changes (e.g., file created/modified), triggers an audit entry if it crosses a gate boundary |
| Project-level index | Updated atomically with each audit entry append — reads existing index, appends new entry, writes back |

### 3.4 Reconstruction Test Design

The acceptance criterion is that the **full history of any completed task can be reconstructed from its audit data alone**:

1. Read AUDIT_LOG.json
2. Walk entries in order (sorted by timestamp + auditId)
3. Rebuild state machine: start at S0, apply each transition's fromState→toState
4. Verify all 4 gate decisions are present with correct authority
5. Verify rework loops if any (same task appearing in multiple transitions)
6. Compare reconstructed path against known task history from task artifacts

This test is the core of `test_audit_log.py` and must pass for every scenario listed below.

---

## 4. Implementation Plan

### 4.1 Files to Create/Modify

#### New File: `ds_eo_openclaw/workflow/audit_log.py` (~120 lines)

```python
"""DS-EO Audit Trail — Phase 2 Integration.

Produces schema-compliant audit entries per EXECUTION_MODE_ARCHITECTURE.md §10.2.
Uses uuid, datetime (standard library), and JSON for persistence.
"""
import json
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

class AuditEntry:
    """Immutable audit entry matching the 14-field schema from §10.2."""
    # ... fields + constructor with UUID generation and ISO-8601 timestamp
    
class AuditLog:
    """Per-task audit log manager. Creates AUDIT_LOG.json in task directory."""
    
    @staticmethod
    def create(task_dir: str, task_id: str) -> "AuditLog":
        """Create new per-task audit log at TASK_<id>/AUDIT_LOG.json"""
    
    def append_entry(self, transition_key: str, from_state: str, to_state: str,
                     gate_passed: Optional[str], gate_status: str,
                     agent_id: str, execution_mode: str, triggered_by: str,
                     details: Dict[str, Any], verified_artifacts: List[str]) -> AuditEntry:
        """Create and append a full audit entry. Returns the entry."""
        # Compute reconstructionHash from preceding entries
        
    def get_entries(self) -> List[AuditEntry]:
        """Read all entries back for verification."""

class ProjectAuditIndex:
    """Project-level index for cross-task audit navigation."""
    
    @staticmethod
    def update(task_id: str, latest_state: str, last_audit_time: str):
        """Append/update entry in docs/reports/AUDIT_INDEX.json"""
```

#### New File: `tests/test_audit_log.py` (~100 lines)

- Schema validation test (all 14 fields present, correct types)
- Persistence verification (append + read back = same entries)
- Reconstruction tests for 6 scenarios:
  1. Approved pass (S0→G1→S2→S3→S4→S5→S6→S7 all clean)
  2. G2 fail (S0→...→S2→S3→S2 rework)
  3. G3 reject (S0→...→S5→S8→S2 rework)
  4. G4 reject (S0→...→S6→S2 rework)
  5. Rework loop (G3 reject → implement → G3 approve)
  6. Blocker encountered (blocker entry + resolution)

#### Modify: `ds_eo_openclaw/workflow/state_engine.py`

- Replace partial dict in `auto_advance()` with full `AuditEntry` creation via `audit_log.AuditLog.append_entry()`
- Include gateStatus (always present, never null), verifiedArtifacts array, proper executionMode
- Manual transition paths also create audit entries via the same module

---

## 5. Acceptance Criteria

### Audit Schema Compliance
- [ ] All 14 required fields present in every entry
- [ ] `auditId` is valid UUID (version 4)
- [ ] `timestamp` is ISO-8601 UTC
- [ ] `gateStatus` is always present (never null), values from {APPROVED, REJECTED, CHANGES_REQD}
- [ ] `reconstructionHash` chain is contiguous and verified for integrity

### Audit Integration with State Engine
- [ ] `auto_advance()` in automatic mode creates full AuditEntry per transition
- [ ] Manual mode transitions also create audit entries (via audit_log module)
- [ ] Per-task AUDIT_LOG.json created at first entry time
- [ ] Project-level AUDIT_INDEX.json updated atomically with each entry

### Reconstruction Verification
- [ ] Full history of any completed task is reconstructable from AUDIT_LOG.json alone
- [ ] All 4 gate decisions are present with correct authority
- [ ] Rework loops are correctly identified and reconstructed
- [ ] State machine path reconstruction matches expected sequence for all 6 test scenarios

### Testing
- [ ] All tests pass (`python -m pytest tests/test_audit_log.py`)
- [ ] Schema validation: every field type verified
- [ ] Persistence: append + read back round-trips correctly
- [ ] Reconstruction: 6 scenarios verified against known expected paths

---

## 6. Risks and Constraints

### Risks
1. **Audit log size growth**: Long-lived tasks with many rework iterations produce large audit files. Addressed in Phase 4 (rotation/archival).
2. **Index corruption on concurrent writes**: Project-level AUDIT_INDEX.json is written by all tasks. Mitigation: atomic file write (write to temp, rename).

### Constraints
1. No external dependencies — JSON files only, standard library (`uuid`, `datetime`, `hashlib`, `json`)
2. Per-task audit at TASK_<id>/AUDIT_LOG.json — not global (right granularity for reconstruction)
3. PM can also create manual-mode entries via the same convenience function

---

## 7. Design Decisions

### Decision: AuditEntry is immutable
Each entry is a snapshot of one transition. Entries are never modified after creation — only appended. This ensures the reconstruction test's integrity chain is valid.

### Decision: Per-task audit + project index (not global-only)
Global-only would require cross-file reads for every reconstruction task. Per-task keeps data co-located with task artifacts, matching the existing DS-EO directory pattern. Project-level index provides fast cross-task navigation without sacrificing local access.

---

## Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ✅ Done | TASK_DS_EO_021 created by CTO |
| G1 (User Approval of Plan) | ⏳ Awaiting | User must approve before Implementer begins |
| G2–G4 | N/A | To be executed after implementation |

---

*CTO Plan produced by: CTO (qwen3.6:35b)*  
*Date: 2026-08-02*
