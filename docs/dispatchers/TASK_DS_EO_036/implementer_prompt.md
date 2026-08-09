# DISPATCH: TASK_DS_EO_036 — DS-EO v0.8 Consolidation & Release

You are the **Implementer**. Execute this plan exactly as written.

## Task: Edit exactly 4 files in /home/deepsim/ds_eo_openclaw/

### Step 1: ds_eo_manifest.yaml
- Change `package.version` to `"0.8.0"` (find and replace the current version line)
- Verify modules list contains: intake, session_health, eo_commands
- Save file

### Step 2: CHANGELOG.md
Add this section at the very TOP of the changelog (after any existing header but before all other content):

```markdown
## [v0.8.0] — 2026-08-09

### Summary
DS-EO v0.8 ships Phases 1–7 as a complete automatic workflow management system:
state engine, audit trail, mode selector, failure/stall handling, comprehensive
test suite (433 tests), session slash commands, and session health monitoring
with real OpenClaw CLI integration.

### Completed Phases
- Phase 1 — PM Workflow State Engine (core state machine)
- Phase 2 — Audit Trail Integration (SHA-256 hash chain entries)
- Phase 3 — User-Facing Mode Selector (/eo mode commands)
- Phase 4 — Failure/Stall Handling Refinements (timeouts, escalation chains)
- Phase 5 — Testing and Validation Suite (92 integration tests)
- Phase 6 — User-Facing /eo Mode Commands (slash command API + 34 tests)
- Phase 7 — Session Health Real OpenClaw API Integration (COMPACT, ARCHIVE, CLOSE CLI)

### Bug Fixes
- Fixed ds_eo_manifest.yaml YAML syntax error in modules section (skill_commands key)
- Fixed agents/pm.md PM→git operations contradiction (AGENTS.md §3 compliance restored)
```

If there's a `## [0.1.0]` or `## [v0.7]` heading at the same level as version sections, leave it but ensure the new v0.8.0 section comes before it.

### Step 3: README.md
- Find all references to `v0.7` and update to `v0.8.0`
- Update any roadmap/release table to show v0.8 shipped
- If there's a "latest release" or "current version" mention, update it

### Step 4: PROJECT_STATUS.md
- Update "Last Updated" to `2026-08-09T12:57:00-07:00`
- Remove TASK_DS_EO_030 revoked entry from Active Tasks table (or mark as REVOKED)
- Mark TASK_DAL_002 as "🔄 Resumed" with note that infra fix resolved the block
- Verify all tasks shown are valid (active or closed — no stale entries)

### Constraints
- NO source code changes anywhere. Only these 4 files.
- Do NOT modify any .py files, tests, protocols, or agents/
- After making changes: run `python3 -m pytest` and confirm 433 pass
- Stage and commit with message: "Consolidate DS-EO v0.8.0 — version bump, changelog, roadmap update"

## Acceptance Criteria
1. ds_eo_manifest.yaml version = "0.8.0"
2. CHANGELOG.md has [v0.8.0] section at top
3. README.md references v0.8.0 as latest
4. PROJECT_STATUS.md cleaned up, updated date
5. All 433 tests still pass
6. All changes committed
