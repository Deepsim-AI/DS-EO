# CTO Implementation Plan — TASK_DS_EO_018

**Date**: 2026-07-31  
**Task**: Document Consistency Sweep  
**Triggered by**: PM workflow audit of all .md files against authoritative sources  

## Problem Statement

After TASK_DS_EO_015+017 (Phase 3 governance migration), protocol/config/role updates were correctly applied but documentation still references the old state (3 roles vs 4, 6 protocols vs 7, Reviewer as read-only).

## Scope

Update documentation across 10+ files to match current reality. Each file identified by PM's sweep with exact discrepancies listed. No structural changes — targeted content corrections only.

## Acceptance Criteria

### README.md
1. ✅ Roles table adds PM (📋) alongside existing 3 roles
2. ✅ Structure tree shows GATE_AUTHORITY_MATRIX.md in protocols/ and pm.md in agents/
3. ✅ Workflow line updated to show PM's lifecycle coordination lane
4. ✅ Roadmap adds Phase 3 completed entry

### ARCHITECTURE.md
5. ✅ Senior Code Reviewer tool policy corrected (write allowed for REVIEW_REPORT.md; deny: [edit, apply_patch])
6. ✅ REVIEW_REPORT.md annotation changed from "(Reviewer → CTO copies)" to "(produced by Reviewer)"
7. ✅ "Three-engineering-organization model" updated to four roles + PM added to diagram
8. ✅ Protocol Hierarchy mentions GATE_AUTHORITY_MATRIX.md as gate governance authority

### INSTALLATION.md
9. ✅ Step 4: "6 protocol files" → "7 protocol files (including GATE_AUTHORITY_MATRIX.md)"
10. ✅ Step 5 (if applicable): Same count update

### protocols/README.md
11. ✅ Categories table adds GATE_AUTHORITY_MATRIX.md as new Governance entry

### examples/minimal-workflow.md
12. ✅ Phase descriptions updated — Reviewer produces own REVIEW_REPORT.md; PM step added to workflow diagram

### AGENTS.md
13. ✅ Task Directory Structure annotation: "(produced by Reviewer)" per current protocol

### ds_eo_manifest.yaml
14. ✅ Compliance check description updated from "All 3 role files" to "All 4 roles" where applicable

## Implementation Approach
- File-by-file targeted edits matching each criterion
- All changes text-level only; no structural reorganization
- Verify each criterion against current authoritative state before marking complete

## Risk Assessment: LOW
All changes are documentation corrections. No code, protocol, or tool-policy impact.
