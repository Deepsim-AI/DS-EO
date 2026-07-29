# Git Initialization Plan — TASK_DS_EO_009

**Task**: TASK_DS_EO_009  
**agent_id**: cto  
**session_id**: _(placeholder — to be filled at execution)_  
**model**: ollama/qwen3.6:35b  
**produced_at**: 2026-07-29T06:52PDT  

---

## Executive Summary

The repository `ds-eo-openclaw` has no `.git` directory — it is unversioned. This single gap undermines every prior claim about what was "implemented" or "deployed" because there is no durable, falsifiable record of changes. STATUS_CHECK.md (TASK_DS_EO_006) demonstrated that the IMPLEMENTATION_REPORT's 11 claimed file changes could not be verified against any committed baseline; only 2 were confirmed by manual inspection.

This plan defines how to initialize version control, establish a reliable baseline, and prevent this class of failure going forward. It addresses requirements 1–8 from the task specification.

---

## Requirement 1: Initial Baseline Scope

### What Should Be Committed (Version-Controlled)

| Directory / File | Reason |
|-----------------|--------|
| `ds-eo-openclaw/protocols/*` (all `.md`) | **Core product** — the protocol definitions that install.sh ships. Must be tracked. |
| `ds-eo-openclaw/templates/*` | Core templates used by all tasks. |
| `ds-eo-openclaw/scripts/*` | Deploy and verification scripts. Source of truth for deployment. |
| `ds-eo-openclaw/agents/*.md` | Agent prompt definitions. Part of the product config. |
| `ds-eo-openclaw/config-templates/*` | Templates that generate openclaw.json — part of the deployable product. |
| `ds-eo-openclaw/tests/*` (excluding `__pycache__/`) | Test code is part of the product. |
| `ds-eo-openclaw/docs/development/reports/TASK_*/` | **All task artifacts** — every report, plan, review, and approval document. These are the audit trail for the development process itself. |
| `ds-eo-openclaw/docs/prompts/*.md` | Agent prompt definitions. |
| `ds-eo-openclaw/docs/development/protocols/*` | Per-project protocol copies (if they exist). |
| `ds-eo-openclaw/CHANGELOG.md`, `CHANGELOG_PHASE1.md` | Version history within the project. |
| `ds-eo-openclaw/ARCHITECTURE.md`, `ROADMAP.md`, `INSTALLATION.md`, etc. | Core documentation. |
| `ds-eo-openclaw/BOOTSTRAP.md`, `ds_eo_manifest.yaml`, `agents_list.json` | Product configuration source files. |
| `.gitignore` (this repo's own) | Essential for correct version control. |

### What Should NOT Be Committed

| Path / Pattern | Reason |
|----------------|--------|
| `*.py[cod]`, `__pycache__/`, `.pytest_cache/` | Generated Python artifacts. |
| `~/.openclaw/protocols/*.ds-eo-bak` | Installation backup files — ephemeral, recreate from repo source. |
| `~/.openclaw/agents/*/sessions/*` | Session trajectory files. Large, ephemeral, environment-specific. |
| `~/.openclaw/state/*` | Runtime SQLite database (OpenClaw state). |
| `~/.openclaw/logs/*` | Log files — runtime-only. |
| `~/.openclaw/cache/*` | Cache — transient. |
| `~/.openclaw/workspace/*` | OpenClaw's own internal workspace code. **Not part of this project.** |
| `~/.openclaw/backups/*.bak` | OpenClaw backup files. |
| `~/.openclaw/plugins/*`, `~/.openclaw/skill-workshop/*` | External plugin/workspace files. |
| `~/.openclaw/identity/*`, `~/.openclaw/devices/*` | Device auth and pairing — sensitive, environment-specific. |
| `*.attested` (workspace-attestations) | Runtime attestation artifacts. |
| **`openclaw.json`** (full path in `.openclaw/`) | Contains auth tokens, port bindings, and secrets. Never commit raw gateway config. However, `config-templates/example_openclaw_config.json` should be committed with placeholders. |

### What About `~/.openclaw/` — The Gateway Config?

The current architecture deploys from repo source (`ds-eo-openclaw/protocols/`) to the install target (`~/.openclaw/protocols/`). The `~/.openclaw/openclaw.json` is the **runtime config** — it contains secrets (auth tokens) and environment-specific values that should never be committed.

However, we need to version-control one file that is currently missing from repo:

- **`~/.openclaw/protocols/implementation_protocol.md`** — This file exists on disk but not in the repo source. It must either be added to `ds-eo-openclaw/protocols/` (and thus committed) or removed from `~/.openclaw/protocols/` if it is truly not part of the product. There should be no gap between what exists locally and what the repo says exists.

**Decision**: Add a copy of `implementation_protocol.md` to `ds-eo-openclaw/protocols/` as part of this task's implementation, commit it, and remove the orphaned copy from `~/.openclaw/protocols/`. This is required by requirement 5.

---

## Requirement 2: .gitignore Proposal

The existing `.gitignore` in the repo is minimal (7 lines). The following should be added to prevent accidental tracking of ephemeral and environment-specific files, while ensuring all source files are tracked:

```gitignore
# ─── Python artifacts ──────────────────────────────────────
__pycache__/
*.py[cod]
*.pyo
.pytest_cache/

# ─── OS / editor noise ────────────────────────────────────
.DS_Store
Thumbs.db
*.swp
*.swo
*~

# ─── Generated by install (ephemeral) ─────────────────────
agents_list.json          # Regenerated by config scripts
*.ds-eo-bak               # Installation backup copies — recreate from repo source

# ─── Session data (never version-control) ──────────────────
*/sessions/
*.trajectory.jsonl
*.trajectory-path.json
*.jsonl.reset.*

# ─── OpenClaw runtime state ───────────────────────────────
openclaw.sqlite*
openclaw.json             # Contains auth tokens — never commit
openclaw.json.bak*
*.bak                     # General backup files
*.attested                # Workspace attestation artifacts

# ─── Model / binary artifacts ─────────────────────────────
*.bin
ollama_models/            # If any local model cache exists in this repo path
```

### Additional Notes on .gitignore Design

1. **Protocol source files are tracked**: `protocols/*.md` files in the repo source (`ds-eo-openclaw/protocols/`) are NOT covered by the `.gitignore` above — they will be committed. Only generated copies (`.ds-eo-bak`) and runtime-deployed copies elsewhere are excluded where appropriate.
2. **Task reports are tracked**: `docs/development/reports/TASK_*/` is not in the gitignore, so all task artifacts are version-controlled. This is intentional — they are the audit trail.
3. **No global `~/.openclaw/` ignore**: This repo (`ds-eo-openclaw`) only covers itself. The OpenClaw runtime directory (`~/.openclaw/`) should NOT have its contents committed; if someone runs `git add ~/.openclaw/` they'd need to understand what they're doing. We document this in the contributing guide.

---

## Requirement 3: Repository Workflow Going Forward

### Commit Responsibility by Stage

| Stage | Coordinator | Executor | Approver | Notes |
|-------|------------|----------|----------|-------|
| Verify task is complete | PM (once exists) | — | CTO | PM confirms all artifacts exist per `verify_task_artifacts.sh` |
| Prepare commit message | PM | Implementer | CTO | PM drafts; CTO approves for significant changes |
| Execute local Git commit | — | Implementer | CTO | Implementer runs the actual `git add`, `git commit` |
| Create git tag | — | Implementer | CTO | For milestones/releases (not every task) |
| Push to remote (if any) | PM | Implementer | CTO + User | User approval required for remote push |

### Connection to Existing TASK_DS_EO_007b Responsibility Table

The existing table in `PM_ROLE_PLAN.md` states:

> "Local Git commit — Coordinates (PM), Approves milestone (CTO), Usually executes (Implementer)"

This plan formalizes that split:

- **PM** verifies that all artifacts exist, passes the verification script, and proposes the commit message.
- **CTO** reviews the proposed changes (diff) and approves the commit plan (Gate G4 for major milestones, gate-level approval per existing workflow).
- **Implementer** executes `git add`, `git commit -m "..."`, and optionally `git tag` / `git push`.

The Implementer never commits without PM's verification confirmation AND CTO's approval.

### Commit Frequency

- **Per-task basis**: Each task that produces verified artifacts gets a commit. This is the minimum useful granularity — it ensures every change is tied to a verifiable task boundary.
- **No "squash everything"**: Do not batch multiple tasks into one commit without explicit CTO approval. Each task's artifacts must remain traceable to its own TASK_ID via git log.

### Commit Message Convention

```
TASK_<id>: <summary>

[Body if needed]

Refs: ds-eo-openclaw/docs/development/reports/TASK_<id>/
```

Example:
```
TASK_DS_EO_009: Initialize version control and establish baseline

First commit of ds-eo-openclaw with complete protocol, template,
and script source. Includes implementation_protocol.md added to
protocols/ directory.

Known issues present in baseline (noted by STATUS_CHECK.md):
- review_protocol.md and approval_protocol.md lack session-isolation rules
  (pending TASK_DS_EO_006 re-implementation)
- reviewer workspace not yet wired to gateway config for persona loading

Refs: ds-eo-openclaw/docs/development/reports/TASK_DS_EO_009/GIT_INIT_PLAN.md
```

### Branch Strategy (Minimal)

For now, maintain a single `main` branch. If collaboration increases, consider `develop` with PRs to `main`, but that is out of scope for initial git initialization.

---

## Requirement 4: Updating Deploy Scripts for Known-Good Commits

### Problem

Currently, `deploy_protocols.sh` and `install.sh` deploy from whatever state exists in the working directory (`$PKG_ROOT/protocols`). If uncommitted changes exist (or worse, files were created locally but not committed — like TASK_DS_EO_006's protocol changes), the installer may ship stale or inconsistent versions.

### Proposed Fix for `deploy_protocols.sh`

Add a **pre-flight integrity check** that verifies the source directory matches the last known-good git commit:

```bash
# ─── Pre-flight Integrity Check ────────────────────────────

verify_deploy_source() {
    local repo_root
    repo_root="$(cd "$PKG_ROOT/.. && pwd")"  # ds-eo-openclaw root
    
    if [ ! -d "$repo_root/.git" ]; then
        echo "⚠ WARNING: No .git found in $repo_root — deploy source cannot be verified."
        echo "   Deploying from working directory state. Commit your changes first." >&2
        return 1  # Non-zero to warn but allow (for first-time use)
    fi
    
    local uncommitted
    uncommitted="$(cd "$repo_root" && git diff --stat HEAD -- '*.md' '*.sh' '*.json' '*.yaml' 2>/dev/null | wc -l)"
    
    if [ "$uncommitted" -gt 0 ]; then
        echo "⚠ WARNING: $uncommitted uncommitted file(s) in deploy source." >&2
        echo "   Consider committing before deploying to ensure reproducible installs." >&2
        # Allow but warn — the installer can still proceed
    fi
    
    local staged
    staged="$(cd "$repo_root" && git diff --cached --stat 2>/dev/null | wc -l)"
    if [ "$staged" -gt 0 ]; then
        echo "⚠ WARNING: $staged staged but uncommitted file(s)." >&2
    fi
    
    return 0
}

# Called at the top of deploy mode, before any file operations
```

### Proposed Fix for `install.sh`

Add a similar check before Step 4 (protocol deployment):

```bash
log "Verifying repository integrity..."
if ! bash "$SCRIPT_DIR/deploy_protocols.sh" --verify-source; then
    err "Deploy source integrity check failed. See above warnings."
fi
```

### Future: Tag-Based Deployment (Recommended Phase 2)

Once the baseline is established, update both scripts to optionally deploy from a tagged commit:

```bash
# In deploy_protocols.sh — new option
if [[ "${1:-}" == "--from-tag" ]]; then
    TAG="$2"
    git -C "$PKG_ROOT/.." checkout "$TAG" -- protocols/ || { echo "Tag not found"; exit 1; }
    # Proceed with normal deployment using checked-out files
fi
```

This ensures installers always produce identical output for a given tag. The default behavior (current working directory) remains for development use but emits warnings when uncommitted changes exist.

### Error Thresholds

| Condition | Behavior |
|-----------|----------|
| No `.git` at all | **Warning** — deploy proceeds from working state (first-time setup) |
| Uncommitted changes to protocol files | **Warning + log** — deploy proceeds but logs the count |
| Uncommitted changes to scripts being deployed | **Hard fail** — scripts are about to change while running; do not proceed |
| Deploy target differs from repo source on all files | **Hard fail** with diff output — something is fundamentally wrong |

---

## Requirement 5: Fixing implementation_protocol.md's Accidental Survival

### Current State

`implementation_protocol.md` exists at `~/.openclaw/protocols/implementation_protocol.md` (created 2026-07-28T18:32) but does not exist in `ds-eo-openclaw/protocols/`. It survived today's install because `deploy_protocols.sh` never deploys it — it is not in the PROTO_FILES array.

### Implementation Steps (for Implementer, separate task)

1. **Review content**: Read `~/.openclaw/protocols/implementation_protocol.md` and confirm it matches what TASK_DS_EO_006's IMPLEMENTATION_REPORT described. If it does, treat this file as the authoritative source; if not, produce a corrected version.

2. **Add to repo**: Copy (or create) `ds-eo-openclaw/protocols/implementation_protocol.md` from the verified content.

3. **Add to deploy pipeline**: Update `deploy_protocols.sh`'s PROTO_FILES array:
   ```bash
   PROTO_FILES=(
       approval_protocol.md
       communication_protocol.md
       completion_protocol.md
       delegation_protocol.md
       handoff_protocol.md
       implementation_protocol.md    # NEW — added by TASK_DS_EO_009
       review_protocol.md
   )
   ```

4. **Update rollback**: The rollback logic already handles any file in PROTO_FILES, so no changes needed there.

5. **Remove orphan**: After successful deployment from repo source, verify `~/.openclaw/protocols/implementation_protocol.md` matches the deployed copy and remove it as a separate file if it was manually placed.

6. **Commit**: All of the above in a single commit for TASK_DS_EO_009.

---

## Requirement 6: Verification Step Connecting to Identity Metadata

### The Problem

The existing `verify_task_artifacts.sh` validates identity metadata (agent_id, session_id, model, produced_at) from artifact headers and checks role independence. However, it operates on **uncommitted file state** — there is no way to verify that "the Implementer claims to have changed files X, Y, Z" against an actual committed diff.

### Proposed Addition: Commit Hash Verification Phase

Add a **Phase 4** to `verify_task_artifacts.sh` (or create a separate verification helper) that requires the IMPLEMENTATION_REPORT.md to include a `commit_hash` field and cross-references it against the repository's actual state:

```bash
# In IMPLEMENTATION_REPORT.md header — REQUIRED for tasks with repo version control:
**commit_hash**: <sha256 of the commit that contains this implementation>
**commit_message**: <exact commit message>

# verify_task_artifacts.sh Phase 4 (new): validate_commit_integrity
validate_commit_integrity() {
    local task_dir="$1"
    local report="${task_dir}/IMPLEMENTATION_REPORT.md"
    
    # Extract claimed commit hash and message from report
    local claimed_hash
    claimed_hash="$(grep '^**commit_hash**:' "$report" | sed 's/^**commit_hash**:[[:space:]]*//' | tr -d ' ')"
    local claimed_msg
    claimed_msg="$(grep '^**commit_message**:' "$report" | sed 's/^**commit_message**:[[:space:]]*//')"
    
    if [ -z "$claimed_hash" ]; then
        report_warn "$report — MISSING commit_hash (version control enabled but no hash recorded)"
        return 1
    fi
    
    local repo_root
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
    
    if [ -z "$repo_root" ]; then
        report_skip "$report — not in a git repository; skipping commit verification"
        return 0
    fi
    
    # Verify the hash exists and produces the claimed message
    local actual_msg
    actual_msg="$(git -C "$repo_root" log -1 --format='%s' "$claimed_hash" 2>/dev/null)"
    
    if [ "$actual_msg" != "$claimed_msg" ]; then
        report_fail "$report — commit hash $claimed_hash exists but message mismatch"
        report_fail "  Expected: '$claimed_msg'"
        report_fail "  Actual:   '$actual_msg'"
        return 1
    fi
    
    # Verify that the diff for this commit contains the files claimed in the report
    local claimed_files
    claimed_files="$(grep -A 50 'Changes Made' "$report" | grep '^|' | wc -l)"
    local actual_modified
    actual_modified="$(git -C "$repo_root" diff --stat "$claimed_hash"^.."$claimed_hash" 2>/dev/null | tail -1 | grep -o '[0-9]* file' | grep -o '[0-9]*')"
    
    if [ "$actual_modified" -gt 0 ]; then
        report_pass "Commit $claimed_hash exists with message: '$actual_msg'"
        report_info "  Modified files in commit: $actual_modified (claimed in report: $claimed_files)"
    fi
    
    return 0
}
```

### Connection to Existing Identity Metadata

The `commit_hash` field is **orthogonal** to the existing identity metadata fields (`agent_id`, `session_id`, `model`, `produced_at`). It serves a different purpose:

| Field | Purpose | Verification Mechanism |
|-------|---------|----------------------|
| `agent_id` | Who produced the artifact (identity) | Cross-check across artifacts (IMPLEMENTATION_REPORT ≠ REVIEW_REPORT ≠ CTO_APPROVAL) |
| `session_id` | Which session produced it (isolation) | Compare session IDs across role boundaries |
| `model` | Which model was used (capability/authority) | Confirm each role used its assigned model |
| `produced_at` | When it was produced (timing) | Ensure timestamps are in logical order |
| **`commit_hash`** (new) | What was actually committed to repo (durable change record) | Verify hash exists in git, message matches, diff contains claimed files |

The commit hash is a fourth dimension of verification: **identity metadata proves who did it; the commit hash proves what actually changed**. Together they eliminate the possibility that an IMPLEMENTATION_REPORT claims changes that were never persisted to durable version control — exactly the failure mode STATUS_CHECK.md identified.

### Implementation Requirement for Implementer

Every future task's IMPLEMENTATION_REPORT.md must include:

```markdown
**commit_hash**: <SHA-256 of the task's commit>
**commit_message**: <exact message used in the git commit>
```

The Reviewer verifies these fields against the actual repository state before accepting the task as complete. The CTO approves only after this verification passes.

---

## Requirement 7: Risk — Committing an Unknown Codebase State

### Assessment

STATUS_CHECK.md confirmed that `ds-eo-openclaw/protocols/` and other repo source directories contain files in a partially-unknown state:
- Protocol files lack session-isolation rules that were claimed to be implemented but never committed.
- Template files and verification scripts were updated and are verifiable.
- There is no way to distinguish "intentionally correct" from "accidentally correct" without prior git history.

### Recommendation: **Commit as Baseline with a Known-Issues Annotation**

I recommend committing the current state as the initial baseline, but with an explicit documented note in two places:

1. **In the first commit message**, include the known-issues annotation (see Requirement 3's example).

2. **Create `docs/development/reports/TASK_DS_EO_009/BASLINE_AUDIT.md`** as part of this task's artifacts, containing:
   - A directory-level inventory of every file that will be committed (with SHA-256 hashes).
   - Explicit listing of known gaps found by STATUS_CHECK.md.
   - A checklist of files that were "missing" from the prior repo source and are now being added.

3. **Tag the first commit** with `v0.2-baseline` to clearly mark this as a pre-release baseline, not a feature-complete milestone.

#### Why Not Audit-First?

Running a "fuller audit" before committing would mean:
- Auditing all 112 repo files for correctness against spec.
- Fixing any discrepancies found.
- Then re-committing.

This is essentially TASK_DS_EO_006 re-implemented plus additional work. Since the protocol gaps are already documented in STATUS_CHECK.md as "known issues" (not hidden bugs), it is more efficient to commit the baseline with transparent annotation and address the known issues as a follow-on implementation task. This follows the principle: **document first, fix second**.

#### What the Known-Issues Annotation Will Say

```
KNOWN ISSUES IN THIS BASELINE:

1. review_protocol.md — Missing session-isolation enforcement rules.
   Status: TRACKED — TASK_DS_EO_006 to re-implement (STATUS_CHECK.md found
   that the original TASK_DS_EO_006 implementation was never committed).

2. approval_protocol.md — Missing session-isolation enforcement rules.
   Status: TRACKED — same as #1 above.

3. handoff_protocol.md — Missing session-isolation transition rules (H-9 through H-12).
   Status: TRACKED — same as #1 above.

4. reviewer agent workspace not wired to gateway config for distinct persona.
   The SOUL.md and IDENTITY.md exist at ~/.openclaw/agents/reviewer/ but openclaw.json
   points all agents to /home/deepsim/agent_system (shared generic SOUL.md).
   Status: TRACKED — separate implementation task required.

5. No git version control existed prior to this commit. All prior claims about
   "implemented" or "deployed" changes are unverifiable for this baseline.
   Everything committed here becomes the authoritative source of truth from this point forward.
```

### Verdict

**Commit now with documented known issues.** The cost of delay (additional audit effort, continued inability to verify any future work) exceeds the cost of committing a "dirty" baseline with transparent annotation. Future tasks will progressively fix the known issues against this new baseline, and each fix will be verifiable via git diff.

---

## Requirement 8: Planning Only — No Implementation

This document is the plan only. The following is explicitly NOT done here:

- ❌ No `git init` commands
- ❌ No `.gitignore` changes to actual files
- ❌ No file modifications, deletions, or creations
- ❌ No protocol file edits
- ❌ No deploy script updates

All of these are reserved for the Implementer (separate task) and must be reviewed by the Development Reviewer before CTO final approval.

---

## Plan Summary

| Req | Proposal | Status in This Plan |
|-----|----------|-------------------|
| 1. Baseline scope | Committed: all repo source + task artifacts. Excluded: runtime config, session data, generated files, secrets. | ✅ Defined |
| 2. .gitignore | Comprehensive rules for Python artifacts, session data, OpenClaw state, backups. Protocol templates scripts are tracked. | ✅ Written |
| 3. Workflow | PM coordinates → CTO approves → Implementer executes commits per-task. Connects to TASK_DS_EO_007b table. | ✅ Defined |
| 4. Deploy script changes | Pre-flight integrity check for uncommitted changes. Tag-based deployment option for future. Hard-fail on script changes while running. | ✅ Proposed |
| 5. implementation_protocol.md | Add to repo source + PROTO_FILES + deploy pipeline + remove orphan from ~/.openclaw/protocols/. | ✅ Defined |
| 6. Commit hash verification | New `commit_hash` field in IMPLEMENTATION_REPORT.md; Phase 4 in verify_task_artifacts.sh. Orthogonal to identity metadata — adds the "what actually changed" dimension. | ✅ Proposed |
| 7. Baseline risk | **Recommendation**: commit now with documented known-issues annotation and `v0.2-baseline` tag. Document gaps transparently rather than delay audit. | ✅ Recommended |
| 8. Planning only | Explicitly deferred to Implementer + Reviewer in subsequent task. | ✅ Enforced |

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Initial baseline includes stale/unverified protocol content | Medium | Documented known-issues list in commit message and BASLNE_AUDIT.md. Follow-on task required to fix protocols. |
| Auth token exposure if openclaw.json accidentally committed | Critical | .gitignore explicitly excludes `openclaw.json` and all `.bak*` files. Contributor documentation added. |
| Session trajectory bloat in future repos | Medium | .gitignore covers `*/sessions/` and all `*.trajectory.*` patterns. Documented in contributing guide. |
| Deploy from stale working directory without detection | Low | Pre-flight integrity check + warnings prevents silent drift between repo source and deployed files. |

---

## Implementation Readiness

This plan is complete and ready for implementation handoff. The following artifacts are produced by the CTO:

- `GIT_INIT_PLAN.md` — This document (the approved plan)
- `BASLNE_AUDIT.md` — Will be produced by the Implementer as part of execution, containing per-file inventory with SHA-256 hashes and known-issues annotation.

Acceptance criteria for implementation (to be verified by Development Reviewer):

1. `.git` directory created in `/home/deepsim/ds-eo-openclaw/`
2. All source files committed as initial baseline
3. `.gitignore` properly excludes ephemeral/generated/sensitive files
4. `implementation_protocol.md` added to repo source and PROTO_FILES
5. `deploy_protocols.sh` updated with integrity check
6. First commit tagged `v0.2-baseline`
7. Known issues documented in `BASLNE_AUDIT.md`

---

*Planned by: CTO Agent (ollama/qwen3.6:35b)*  
*Gate: G1 — Plan Approval Pending User Review*
