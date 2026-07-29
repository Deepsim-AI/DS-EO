# CTO Plan — TASK_20260729_001

**Task ID**: TASK_20260729_001  
**Title**: Phase 2 — Self-Hosting (DS-EO Develops DS-EO)  
**Date**: 2026-07-28  
**Role**: CTO / Architect (ollama/qwen3.6:35b)  
**Status**: AWAITING USER APPROVAL  

---

## Executive Summary

Phase 2 validates the engineering organization by having DS-EO develop itself. This is done in three sub-tasks, each following the standard four-phase workflow:

1. **Sub-task 1**: Create a DS-EO-specific workspace with proper AGENTS.md that defines the build-time organization and delegates to the runtime product
2. **Sub-task 2**: Update openclaw.json agent configs so the three engineering agents work in ds-eo-openclaw/ as their workspace, not agent_system/
3. **Sub-task 3**: Execute a real self-hosting task cycle — create a new task inside ds-eo-openclaw/, implement it using the deployed DS-EO agents, validate the workflow end-to-end

No architectural changes to the package itself. The package (agents/, protocols/, templates/, scripts/, tests/) remains untouched. Only configuration and governance files are modified.

---

## 1. Problem Statement

DS-EO is built but its workspace is agent_system/ (the DS-AIOS runtime product). This creates a category error: the engineering organization builds itself *inside* the product's repository rather than in its own isolated space. Self-hosting requires:

- A proper `AGENTS.md` in ds-eo-openclaw/ that establishes the build-time organization
- Agent workspace pointing to ds-eo-openclaw/ (not agent_system/)
- Validation that the workflow functions for real work within the canonical repository

---

## 2. Current State Analysis

### 2.1 What's Already Deployed

| Component | Location | Status |
|-----------|----------|--------|
| DS-EO package (all artifacts) | `/home/deepsim/ds-eo-openclaw/` | ✅ Complete (42 files, v0.1) |
| OpenClaw agent configs | `~/.openclaw/openclaw.json` → agents.list[] | ✅ 3 agents configured (cto, implementer, reviewer) |
| Global protocols | `~/.openclaw/protocols/*.md` (6 files) | ✅ All deployed |
| Agent prompts (source) | `ds-eo-openclaw/agents/*.md` (3 files) | ✅ In package |
| Agent prompts (deployed) | `agent_system/docs/prompts/*.md` (3 files) | ✅ Deployed to agent_system |

### 2.2 What's Missing for Self-Hosting

| Gap | Current State | Required State |
|-----|--------------|----------------|
| DS-EO workspace AGENTS.md | None exists | Create `ds-eo-openclaw/AGENTS.md` with build-time org definition |
| Agent workspace dir | All 3 agents → `/home/deepsim/agent_system/` | Agents → `/home/deepsim/ds-eo-openclaw/` |
| ds-eo-openclaw/ dev infrastructure | No `docs/development/protocols/`, no template dirs | Create dev directory structure within the repo |
| Self-hosting validation | N/A | Execute one real task cycle inside ds-eo-openclaw/ |

### 2.3 Key Architectural Insight

OpenClaw loads agent context via workspace-level bootstrap files (AGENTS.md, SOUL.md, TOOLS.md, etc.) injected as "Project Context." The three DS-EO agents currently point to `agent_system/` where AGENTS.md contains both:
- §1–§2: Two-layer model concept + runtime product architecture
- §3–§9: Build-time organization (CTO/Implementer/Reviewer) rules

For self-hosting, ds-eo-openclaw/ needs its own AGENTS.md that:
- Defines the build-time organization (CTO → Implementer → Reviewer → CTO workflow)
- References the DS-EO package components (agents/, protocols/, templates/) as the authoritative source
- Does NOT define any runtime product (there is no shipped product — DS-EO is the product)
- Establishes ds-eo-openclaw/ as both workspace and canonical repo

---

## 3. Proposed Changes

### 3.1 Sub-task A: Create ds-eo-openclaw AGENTS.md

**New file**: `ds-eo-openclaw/AGENTS.md`

This AGENTS.md is the **only** workspace-level role definition for self-hosted DS-EO. It establishes:

```
Two-Layer Model (self-referential)
┌──────────────────────────────────────────────────┐
│ Layer 1: Build-Time Engineering Organization     │  ← DS-EO itself (CTO+Implementer+Reviewer)
│   - CTO: Architecture, planning, approval        │
│   - Implementer: Execute approved plans           │
│   - Reviewer: Independent quality verification    │
├──────────────────────────────────────────────────┤
│ Layer 2: Runtime Product                         │  ← Not applicable in v0.1
│   (DS-EO is the product; there is no deeper       │
│    runtime layer yet)                             │
└──────────────────────────────────────────────────┘

Source of truth for this workspace's build-time org:
- ds_eo_manifest.yaml (package identity)
- agents/*.md (role prompts — authoritative source)
- protocols/ (engineering rules — authoritative source)
- templates/ (document formats — authoritative source)
```

Unlike `agent_system/AGENTS.md`, this file does NOT contain runtime agent definitions. It is purely the engineering organization's own self-description and governance rules, with references pointing to its own package files.

### 3.2 Sub-task B: Update openclaw.json Agent Configs

**Modified**: `~/.openclaw/openclaw.json` → agents.list[]

Change all three DS-EO agents' workspace from `/home/deepsim/agent_system/` to `/home/deepsim/ds-eo-openclaw/`:

```json
{ "id": "cto",        "workspace": "/home/deepsim/ds-eo-openclaw/" }
{ "id": "implementer", "workspace": "/home/deepsim/ds-eo-openclaw/" }
{ "id": "reviewer",   "workspace": "/home/deepsim/ds-eo-openclaw/" }
```

**Safety**: Use backup before change (per delegation_protocol). Update is a simple 3-line JSON edit. No other config sections affected.

### 3.3 Sub-task C: Create Dev Infrastructure in ds-eo-openclaw/

Create the standard development directory structure within the canonical repo:

```
ds-eo-openclaw/docs/development/
├── protocols/                    ← DS-EO protocol copies (already in packages/, mirror here for workspace)
│   ├── README.md                 ← Protocol hierarchy guide
│   ├── approval_protocol.md
│   ├── communication_protocol.md
│   ├── completion_protocol.md
│   ├── delegation_protocol.md
│   ├── handoff_protocol.md
│   └── review_protocol.md
└── reports/                      ← Task history (already exists for TASK_DS_EO_001, TASK_DS_EO_002)
    ├── TASK_DS_EO_001/
    └── TASK_DS_EO_002/
```

This is purely a structural setup — the protocol files are symlinks or copies from `ds-eo-openclaw/protocols/`. Task reports remain as-is.

### 3.4 Sub-task D: Execute Self-Hosting Validation Cycle

After configuration, execute one real task cycle inside ds-eo-openclaw/:

1. **Task creation**: Create a new TASK (e.g., `TASK_DS_EO_003`) with a CTO plan
2. **Implementation**: Have the Implementer execute changes within ds-eo-openclaw/
3. **Review**: Have the Reviewer verify against the plan
4. **Approval**: CTO issues final approval

The task itself should be something useful but bounded — for example, adding a `ROADMAP.md` to ds-eo-openclaw/ documenting the transition from v0.1 to v0.2, or updating the CHANGELOG with Phase 2 milestone entries.

---

## 4. Detailed Implementation Plan

### Phase A: Create ds-eo-openclaw AGENTS.md

#### Content of AGENTS.md

```markdown
# AGENTS.md — DS-EO Engineering Organization

This file governs how the engineering organization works within this workspace.

## Two-Layer Model

Layer 1 (Build-Time): The engineering team that develops software.
Layer 2 (Runtime Product): What gets built at deployment time.

For v0.1, DS-EO is the product — Layer 2 is not yet applicable.

## Engineering Organization

### CTO / Architect 🏗️
- Model: `ollama/qwen3.6:35b`
- Role: Architecture, planning, final approval authority
- Tools: Read-only (write/edit/apply_patch denied)
- Authority: Creates TASK directories, assigns IDs, approves implementations

### Code Implementer 💻
- Model: `ollama/ornith:35b`  
- Role: Execute approved plans, produce working code
- Tools: Full repository access
- Constraint: Follow CTO plan exactly

### Senior Code Reviewer 🔍
- Model: `ollama/laguna-xs-2.1:q4_K_M`
- Role: Independent quality verification
- Tools: Read-only (write/edit/apply_patch denied)
- Constraint: Cannot modify files, only reads and reports

## Source of Truth

The authoritative source for all engineering organization components is the 
package itself at `ds-eo-openclaw/`:

| Component | Location | Description |
|-----------|----------|-------------|
| Role definitions | agents/*.md | Portable agent prompts with model placeholders |
| Engineering protocols | protocols/ | Core rules, gates, workflows (authoritative) |
| Document templates | templates/ | Task lifecycle document formats |
| Package manifest | ds_eo_manifest.yaml | Single source of truth for package contents |
| Configuration examples | config-templates/ | Reference configs for deployment |

## Development Workflow

All implementation work follows the four-phase sequence:

```
User Request → CTO Plan (G1) → Implementer (G2) → Reviewer (G3) → CTO Approve (G4)
```

Four formal approval gates ensure quality at every phase transition.

See `protocols/` for detailed gate definitions and protocol rules.

## Task Management

Tasks use `docs/development/reports/TASK_<YYYYMMDD>_<NNN>/`:

```
TASK_<id>/
├── CTO_PLAN.md              # Architecture analysis + plan (CTO produces)
├── IMPLEMENTATION_REPORT.md  # Changes, tests, decisions (Implementer produces)
├── REVIEW_REPORT.md          # Findings and recommendation (Reviewer → CTO copies)
└── CTO_APPROVAL.md           # Final approve/reject with rationale (CTO produces)
```

## Architecture Preservation

No unauthorized refactoring of existing package files. All architectural changes 
require a formal CTO proposal and user approval.
```

### Phase B: Update openclaw.json Agent Configs

**Before**:
```json
{"id": "cto", "workspace": "/home/deepsim/agent_system", ...}
{"id": "implementer", "workspace": "/home/deepsim/agent_system", ...}
{"id": "reviewer", "workspace": "/home/deepsim/agent_system", ...}
```

**After**:
```json
{"id": "cto", "workspace": "/home/deepsim/ds-eo-openclaw/", ...}
{"id": "implementer", "workspace": "/home/deepsim/ds-eo-openclaw/", ...}
{"id": "reviewer", "workspace": "/home/deepsim/ds-eo-openclaw/", ...}
```

### Phase C: Create Dev Infrastructure

Symlink approach (preserves single source of truth):

```bash
# Protocol mirrors for workspace access (symlinks to package sources)
mkdir -p ds-eo-openclaw/docs/development/protocols
ln -sf ../../protocols/*.md ds-eo-openclaw/docs/development/protocols/
ln -sf protocols/README.md ds-eo-openclaw/docs/development/protocols/README.md
```

This ensures the workspace-level `docs/development/protocols/` mirrors the package's `protocols/` without duplicating content. If symlinks are not supported, use copies with a clear comment that they are synchronized with the package source.

### Phase D: Self-Hosting Validation

**Task**: `TASK_DS_EO_003 — Add DS-EO v0.2 Roadmap to Package`

This is a real task implemented inside ds-eo-openclaw/:
1. CTO creates CTO_PLAN.md defining a v0.2 roadmap (building on Phase 2 concept)
2. Implementer creates `ROADMAP.md` in the package root
3. Reviewer verifies against plan
4. CTO issues final approval

This validates:
- Agent workspace correctly points to ds-eo-openclaw/ (agents see AGENTS.md and can work within it)
- Task creation, handoff, and approval workflow functions within the canonical repo
- Protocol files are accessible from the new workspace
- The package is truly self-contained and self-developing

---

## 5. Acceptance Criteria

| # | Criterion | Verification Method |
|---|-----------|-------------------|
| A1 | `ds-eo-openclaw/AGENTS.md` created with build-time org definition, source-of-truth table, and governance rules | File exists, content verified against spec above |
| A2 | All 3 DS-EO agents' workspace updated to `/home/deepsim/ds-eo-openclaw/` | `openclaw.json` agents.list[] diff check |
| A3 | Agent backup created before config change | Backup file exists at expected location |
| A4 | `ds-eo-openclaw/docs/development/protocols/` exists with protocol mirrors | File/directory check |
| A5 | Agent configs still valid JSON after merge | Python json.tool validation |
| A6 | Non-DS-EO config sections (gateway, plugins, channels) preserved unchanged | Diff comparison against backup |
| A7 | Self-hosting task cycle completed within ds-eo-openclaw/ | TASK_DS_EO_003 artifacts present in canonical repo |
| A8 | No package files modified during self-hosting work | Package content diff check (AGENTS.md is the only new file; changes are limited to roadmap addition) |

---

## 6. Risks and Mitigations

| # | Risk | Severity | Mitigation |
|---|------|----------|-----------|
| R1 | Agent workspace change breaks current agent_system work | **High** | Keep agent_system/ as-is; new agents point to ds-eo-openclaw/ — OR update existing agents and ensure future agent_system work uses a separate mechanism. **Decision**: Update workspace on all 3 agents (ds-eo-openclaw is now the canonical workspace). Future DS-AIOS work will use a separate agent config or explicit workspace override. |
| R2 | Existing tasks in agent_system/ reference ds-eo-openclaw/ paths | Medium | Document the transition; future tasks in agent_system explicitly note they're "DS-AIOS work, not DS-EO" |
| R3 | Self-hosting task cycle fails to validate because workspace isn't properly recognized | Low | Use `openclaw doctor` or equivalent to verify config validity after changes |
| R4 | Protocol mirrors diverge from package source | Low | Symlinks prevent divergence; if copies used, add sync script |

---

## 7. Implementation Instructions

The Implementer should execute sub-tasks in order:

### Sub-task A
1. Create `ds-eo-openclaw/AGENTS.md` per the spec in §4 Phase A above
2. Verify content matches all governance requirements (role definitions, tool policies, source-of-truth table, workflow description)

### Sub-task B
1. **Backup**: `cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak.ds-eo-selfhost`
2. **Change**: Update workspace field on all 3 DS-EO agents from `/home/deepsim/agent_system/` to `/home/deepsim/ds-eo-openclaw/`
3. **Validate**: `python3 -c "import json; json.load(open('/home/deepsim/.openclaw/openclaw.json'))"` — must not raise
4. **Preserve**: Confirm gateway, plugins, skills, channels sections unchanged

### Sub-task C
1. Create `ds-eo-openclaw/docs/development/protocols/` directory
2. Symlink (or copy) all 7 protocol files from `ds-eo-openclaw/protocols/` 
3. Include README.md in the mirror

### Sub-task D
1. Create task: `TASK_DS_EO_003 — Add v0.2 Roadmap to DS-EO Package`
2. CTO writes CTO_PLAN.md within ds-eo-openclaw/docs/development/reports/TASK_DS_EO_003/
3. Implementer creates ROADMAP.md in ds-eo-openclaw/ root
4. Reviewer verifies and writes REVIEW_REPORT.md
5. CTO issues CTO_APPROVAL.md

---

*Awaiting user approval to proceed.*
