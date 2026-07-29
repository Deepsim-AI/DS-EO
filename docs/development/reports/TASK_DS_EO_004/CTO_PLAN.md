# CTO Plan — TASK_DS_EO_004

**Task ID**: TASK_DS_EO_004  
**Title**: Phase 3 — Production Readiness (Protocol Enforcement, Uninstall, Multi-Host Testing)  
**Date**: 2026-07-28  
**Role**: CTO / Architect (ollama/qwen3.6:35b)  
**Status**: AWAITING USER APPROVAL  

---

## Executive Summary

After the first real self-hosting task cycle (TASK_DS_EO_003), several gaps between protocol documentation and actual enforcement became clear. Phase 3 addresses these through four concrete sub-tasks: adding verification automation for handoff artifacts, creating uninstallation procedures, establishing agent ID conflict detection, and documenting a version migration path. Each sub-task produces actionable artifacts — not more documentation about documentation.

---

## Problem Statement

The first production task cycle exposed 7 gaps between what the protocols describe and what actually happens:

| Gap | Impact | Priority |
|-----|--------|----------|
| Communication protocol JSON types exist but no transport mechanism | Reviewers can't verify handoff quality via standardized messages | Medium |
| Handoff artifacts defined (4 files) but no enforcement | Tasks proceed without proper artifacts; no automated validation | **High** |
| Completion checklists described but not enforced by automation | Gate violations go undetected until CTO finds them | **High** |
| No uninstallation procedure | Can't cleanly remove DS-EO from a host | Medium |
| No version migration path (v0.1 → v0.2) | Upgrade risk for existing installations | Medium |
| No agent ID conflict detection | Two DS-EO orgs colliding on the same host causes silent corruption | **High** |
| Gate G1 "user approves" undefined in self-hosting mode | Ambiguous who holds G1 authority when no external user exists | Low (self-hosted) |

---

## Proposed Changes

### Sub-task A: Handoff Artifact Verification Script

**New file**: `ds-eo-openclaw/scripts/verify_task_artifacts.sh`

A script that validates any task directory has all 4 required artifacts with proper structure:

```bash
# Usage: verify_task_artifacts.sh <task_dir_path>
# Returns: exit 0 on success, exit 1 with gap report on failure
```

Checks each task directory for:
- `CTO_PLAN.md` exists and contains "Acceptance Criteria" section + model/role references
- `IMPLEMENTATION_REPORT.md` exists and contains "Acceptance Criteria Verification" section + test results
- `REVIEW_REPORT.md` exists and contains "Recommendation" field (APPROVE/REJECT/REQUEST_CHANGES) + scoring dimensions
- `CTO_APPROVAL.md` exists and contains "Decision:" with APPROVED/REJECTED

**Why**: The handoff protocol describes the 4 artifacts but no tool enforces their presence or minimum content. This script closes that gap.

### Sub-task B: Uninstallation Procedure

**New file**: `ds-eo-openclaw/scripts/uninstall.sh`

Clean removal of DS-EO from any host:

```bash
# Usage: uninstall.sh [--confirm]
# Removes:
#   1. Agents from openclaw.json (restore from .bak)
#   2. Protocol files from ~/.openclaw/protocols/
#   3. Agent prompts from workspace docs/prompts/
#   4. Protocol copies from project-level docs/development/protocols/
```

**New file**: `ds-eo-openclaw/docs/UNINSTALL.md` — step-by-step uninstall guide for each installation method (scripted, manual merge, ClawHub).

**Why**: No removal procedure exists today. DS-EO cannot be cleanly uninstalled without potentially breaking the host's openclaw.json.

### Sub-task C: Agent ID Conflict Detection

**New file**: `ds-eo-openclaw/scripts/conflict_check.sh`

Before installation, check for conflicts:

```bash
# Usage: conflict_check.sh <openclaw_config_path>
# Checks:
#   1. Do any existing agents have the same IDs as DS-EO (cto, implementer, reviewer)?
#   2. Are there duplicate agent names?
#   3. Does the host have compatible OpenClaw version?
# Output: PASS or FAIL with specific conflict details
```

**New file**: `ds-eo-openclaw/templates/conflict_report_template.md` — standardized format for reporting conflicts when found.

Update `generate_openclaw_config.sh` to call this before merging and abort if critical conflicts detected.

**Why**: Currently, if another DS-EO org is installed on the same host, agent IDs silently overwrite each other in openclaw.json. No validation catches this at install time.

### Sub-task D: Version Migration Procedure (v0.1 → v0.2)

**New file**: `ds-eo-openclaw/scripts/migrate_to_v0.2.sh`

Upgrade path from any v0.1.x to the latest v0.2.x:

```bash
# Usage: migrate_to_v0.2.sh [--dry-run]
# Checks:
#   1. Current installed version (from openclaw.json or package manifest)
#   2. Compatibility with target version
#   3. Protocol version compatibility
#   4. Agent config field changes needed
# Dry run shows diff without applying
# Confirm applies all necessary changes
```

**New file**: `ds-eo-openclaw/UPGRADING.md` — migration guide for each potential breaking change between versions.

**Why**: Today there's no upgrade path. When v0.2 ships, existing hosts would need manual reconciliation of config field changes, protocol updates, and template format changes.

---

## Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|-------------------|
| A1 | `verify_task_artifacts.sh` exists and validates all 4 required files with structure checks | Execute on TASK_DS_EO_003 dir → exit 0; execute on empty dir → exit 1 with gap report |
| B2 | `uninstall.sh` exists, is safe (backup first), restores original config exactly | Run uninstall → verify openclaw.json matches backup byte-for-byte |
| C1 | `conflict_check.sh` detects ID conflicts and compatible host state | Test on clean config → PASS; test with duplicate IDs → FAIL with details |
| D1 | `migrate_to_v0.2.sh` exists with --dry-run mode | Run with --dry-run → shows changes without modifying files |
| E1 | All new scripts pass basic syntax validation (bash -n) | Syntax check passes for each script |
| E2 | No existing package files modified | diff check: only new files added |

---

## Detailed Implementation Plan

### Sub-task A: Handoff Artifact Verification Script

```bash
#!/usr/bin/env bash
# verify_task_artifacts.sh — Validate task directory completeness and structure

REQUIRED_ARTIFACTS=("CTO_PLAN.md" "IMPLEMENTATION_REPORT.md" "REVIEW_REPORT.md" "CTO_APPROVAL.md")

declare -A MINIMUM_SECTIONS=(
    ["CTO_PLAN.md"]="Acceptance Criteria"
    ["IMPLEMENTATION_REPORT.md"]="Acceptance Criteria Verification"
    ["REVIEW_REPORT.md"]="Recommendation"
    ["CTO_APPROVAL.md"]="Decision:"
)

failures=0
for artifact in "${REQUIRED_ARTIFACTS[@]}"; do
    path="$1/$artifact"
    
    # Check existence
    if [ ! -f "$path" ]; then
        echo "MISSING: $artifact — required handoff artifact not found"
        failures=$((failures + 1))
        continue
    fi
    
    # Check minimum size (>50 bytes — not empty)
    size=$(wc -c < "$path")
    if [ "$size" -lt 50 ]; then
        echo "TOO_SMALL: $artifact ($size bytes, min 50)"
        failures=$((failures + 1))
        continue
    fi
    
    # Check required sections
    section="${MINIMUM_SECTIONS[$artifact]}"
    if ! grep -q "$section" "$path"; then
        echo "MISSING_SECTION: $artifact — missing required section '$section'"
        failures=$((failures + 1))
        continue
    fi
done

if [ "$failures" -eq 0 ]; then
    echo "PASS: All 4 artifacts present with required structure"
    exit 0
else
    echo "FAIL: $failures artifact validation failures"
    exit 1
fi
```

### Sub-task B: Uninstallation Procedure

**uninstall.sh**:
- Reads backup at `~/.openclaw/openclaw.json.bak.ds-eo-selfhost` (or first .bak if self-host doesn't exist)
- Removes DS-EO agent entries from agents.list[]
- Restores original openclaw.json byte-for-byte from backup
- Removes protocol files deployed by DS-EO (only those with known markers)
- Removes prompt files deployed by DS-EO (ctos.md, implementer.md, reviewer.md)

**UNINSTALL.md**: Covers three installation methods:
1. Scripted install → run uninstall.sh --confirm
2. Manual merge → restore openclaw.json from backup; remove protocol copies manually
3. ClawHub → uninstall as standard plugin/skill

### Sub-task C: Conflict Detection

**conflict_check.sh**:
- Scans target openclaw.json for agents with IDs `cto`, `implementer`, `reviewer`
- If found and they differ from DS-EO definitions, reports conflict with current values
- Checks OpenClaw version compatibility
- Returns specific recommendations (replace vs rename vs abort)

Update `generate_openclaw_config.sh --merge` to call `conflict_check.sh` first. Abort if critical ID conflicts detected unless `--force` flag used.

### Sub-task D: Version Migration

**migrate_to_v0.2.sh**:
- Reads current version from existing agent config or package manifest
- Validates compatibility range
- Lists all changes needed (config fields, protocol updates, template format changes)
- Dry-run mode shows exact diff without applying
- Confirm mode applies changes with backup before each modification

**UPGRADING.md**: Documents:
- What changes between v0.1 and v0.2
- Breaking changes (if any)
- Rollback procedure if migration fails
- Compatibility matrix for all planned versions

---

## Risks and Mitigations

| # | Risk | Severity | Mitigation |
|---|------|----------|-----------|
| R1 | Uninstall breaks openclaw.json restoration | **High** | Backup first; test on clean host; byte-for-byte comparison post-uninstall |
| R2 | Conflict detection false positives (DS-EO uses same IDs by design) | Low | Only flag if existing agent differs from DS-EO definition; agreeable ID match is not a conflict |
| R3 | Migration script modifies wrong config file | **High** | Verify target path before any write; dry-run required for first migration on each host |
| R4 | Artifact verification too strict (rejects valid tasks) | Medium | Allow configurable minimum sizes; require only existence of all 4 files as hard requirement, content checks as warnings |

---

*Awaiting user approval.*
