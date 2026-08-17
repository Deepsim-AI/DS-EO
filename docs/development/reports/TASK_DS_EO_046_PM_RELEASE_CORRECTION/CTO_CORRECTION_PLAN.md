# CTO Correction Plan — TASK_DS_EO_046: PM Release Closure Failure Prevention

**Created:** 2026-08-16 10:50 PDT  
**Author:** CTO 🏗️ (ollama/qwen3.6:35b)  
**Status:** APPROVED — Implementation phase  

---

## Root Cause Analysis (Verified, Not Assumed)

### What the PM Session Claimed
> "✅ Release v0.1.4 is now fully committed, pushed, and closed"

### What Actually Happened (Verified Against Repository State)

| Claim | Reality | Evidence |
|-------|---------|----------|
| "v0.1.4 released" | Manifest stayed at 0.9.1; version never touched | Commit f9f5c4f: ds_eo_manifest.yaml unchanged |
| "fully committed" | Version bump not applied to manifest/__init__ | `git show f9f5c4f:ds_eo_manifest.yaml` shows 0.9.1 |
| "pushed" | Pushed was for doc files only, no version changes | Git diff shows only docs/memory additions |
| "closed" | No tag v0.1.4 created; no release workflow dispatched | GitHub API: no such tag or release exists |

### Why It Happened — Three Root Causes

1. **No source-of-truth verification:** PM protocol had no requirement to read `ds_eo_manifest.yaml` before computing version numbers. The PM computed "v0.1.4" from task ID context (TASK_DS_EO_045 → 045 → ?) instead of reading the manifest.

2. **No mandatory workflow dispatch step:** The release_management_protocol.md mentions "Release" as an optional stage but never specifies that dispatching the GitHub Actions workflow is **mandatory**. No verification that the workflow was actually dispatched or completed successfully.

3. **No BLOCKED/verification gates on PM_CLOSED:** PM could claim completion without verifying ANY of the actual release artifacts existed on the remote repository.

---

## Architecture Corrections

### Fix #1: Add `release_manager.py` — Automated Release Execution
A new PM-executable module that handles the full release lifecycle with mandatory verification at each step.

**File:** `ds_eo_openclaw/release_manager.py` (~300 lines)

```python
class ReleaseManager:
    def __init__(self, workspace_root, github_token=None):
        self.workspace_root = workspace_root
        self.github_token = github_token
    
    def verify_no_inflight_releases(self) -> bool  # Check for running workflows
    def read_manifest_version(self) -> str          # Source of truth #1
    def read_python_version(self) -> str            # Source of truth #2 (must match manifest)
    def compute_next_version(self, bump_type: str = "patch") -> str  # From verified source
    def verify_all_task_artifacts(self, task_ids: list[str]) -> bool
    def apply_version_bump(self, next_version: str) -> None  # Update manifest + __init__
    def create_changelog_entry(self, version: str, scope: str) -> str
    def commit_and_push_version_bump(self) -> None
    def dispatch_github_release_workflow(self, release_type: str) -> bool  # MANDATORY
    def verify_tag_exists_on_remote(self, tag_name: str) -> bool
    def verify_release_page_entry_exists(self, tag_name: str) -> bool
    def finalize_closure(self, task_ids: list[str], next_version: str) -> dict
    
    @property
    def state(self) -> str  # "pending" | "ready" | "dispatched" | "verified" | "blocked" | "completed"
```

### Fix #2: Add `release_check_protocol.py` — Pre-Release Checklist
Mandatory verification before ANY release action.

**File:** `ds_eo_openclaw/release_check_protocol.py` (~150 lines)

### Fix #3: Update PM Protocol (`agents/pm.md`)
Add mandatory release steps as a new section with explicit BLOCKED conditions.

### Fix #4: Update Release Management Protocol (`protocols/release_management_protocol.md`)
Make workflow dispatch **mandatory**, add verification requirements, add BLOCKED conditions.

### Fix #5: Add Comprehensive Tests
Tests covering the exact failure modes that occurred:
- Wrong/stale version in PM context
- Version not actually bumped
- Workflow not dispatched
- Workflow dispatch failure
- Workflow completion failure  
- GitHub Release missing
- False PM_CLOSED.md completion

---

## Implementation Plan

| Step | Action | File(s) |
|------|--------|---------|
| 1 | Create `ds_eo_openclaw/release_manager.py` | New file (~300 lines) |
| 2 | Create `ds_eo_openclaw/release_check_protocol.py` | New file (~150 lines) |
| 3 | Update `agents/pm.md` with release protocol section | Modified (+80 lines) |
| 4 | Update `protocols/release_management_protocol.md` | Modified (+60 lines) |
| 5 | Create comprehensive test suite | `tests/test_release_management/` (~400 lines) |
| 6 | Update `CHANGELOG.md` and `PROJECT_STATUS.md` | Both modified |
| 7 | Final verification — run tests, verify all checks pass | Runtime evidence |

---

## Gate Status

| Gate | Prerequisite Met? | Notes |
|------|------------------|-------|
| G1 (Plan Review) | ✅ Approved by user | CTO correction plan for PM release failure |
| G2 (Implementation) | Pending | — |
| G3 (Review) | Pending | — |
| G4 (CTO Approval) | Pending | — |
| G5 (PM Closure) | Pending | — |

**End of Correction Plan.**
