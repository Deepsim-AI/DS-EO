# Baseline Audit Report

**Repository:** `ds-eo-openclaw`  
**Baseline Tag:** `v0.2-baseline` (commit `489a03ac`)  
**Generated:** 2026-07-29  
**Purpose:** Immutable record of the initial baseline state for change detection

---

## Summary

| Metric | Value |
|--------|-------|
| Total tracked files | 118 |
| Baseline commit | `489a03ac48c3a49a836ef90b2e4d6351d2a20e2d` |
| Tag | `v0.2-baseline` |
| Branch | `main` |

---

## Baseline State

This file documents the SHA-256 hash inventory of every tracked file at baseline (tag `v0.2-baseline`). It serves as the reference point for all future change detection via `scripts/baseline_audit.sh`.

### Known Issues Documented in Baseline Commit

The initial commit message documents 5 known issues that exist in this baseline:

1. **Missing session-isolation rules** — `review_protocol.md`, `approval_protocol.md`, and `handoff_protocol.md` lack explicit session-scope declarations
2. **Reviewer agent workspace not wired** — Reviewer uses default workspace instead of dedicated reviewer workspace
3. **No prior version control** — This is the first git repository for this project
4. **Incomplete protocol deployment** — `implementation_protocol.md` exists in OpenClaw but is not yet tracked/deployed here
5. **Protocol file duplication risk** — Some files exist in both `protocols/` and `docs/development/protocols/` (identical content)

---

## SHA-256 Inventory

See `scripts/baseline_audit.sh` to regenerate the full hash inventory at any time. The script compares current state against this baseline and reports:
- **Modified files** — tracked files whose content changed
- **New files** — untracked files (potential leaks)
- **Deleted files** — previously tracked files that no longer exist

---

## How to Use

```bash
# Run audit from repository root
cd /home/deepsim/ds-eo-openclaw
./scripts/baseline_audit.sh

# Review output in logs/ directory
cat logs/baseline_audit.log
```

The script performs a hard-fail (exit 1) if any changes are detected, ensuring the baseline is never silently drifted from. To update the baseline after intentional changes:

```bash
# After reviewing and accepting changes
./scripts/update_baseline.sh
```

---

## File Categories at Baseline

| Category | Count | Examples |
|----------|-------|---------|
| Documentation (root) | 16 | AGENTS.md, SOUL.md, README.md, CHANGELOG.md |
| Agent definitions | 5 | agents/*.md, agents_list.json |
| Protocol files | 7+4 | protocols/, docs/development/protocols/ |
| Development reports | ~30 | TASK_DS_EO_*/CTO_PLAN.md, etc. |
| Templates | 12 | templates/*.md |
| Scripts | 10 | scripts/deploy_*.sh, scripts/install.sh |
| Tests | 5 | tests/test_*.py, tests/test_*.sh |
| Config/manifests | 3 | ds_eo_manifest.yaml, openclaw-workspace-state.json |
| Configuration templates | 2 | config-templates/*.json |
| Examples | 1 | examples/minimal-workflow.md |

---

*This file is version-controlled and part of the baseline. Do not modify without updating the checksum inventory.*
