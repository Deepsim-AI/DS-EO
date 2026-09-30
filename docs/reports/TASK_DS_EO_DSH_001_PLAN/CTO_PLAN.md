# CTO_PLAN.md — TASK_DS_EO_DSH_001

**Task:** Project Bootstrap and Migration Definition  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-29  
**Gate:** G1 — Plan for User Review  

---

## 1. Task Objective

Establish the DS-EO DSH Edition project framework: define scope, boundaries, task sequence, artifact structure, acceptance criteria, and repository strategy. **No implementation code is produced in this task.** The output is governance and planning artifacts that prepare TASK_DS_EO_DSH_002 (technical architecture) to follow.

---

## 2. Project Purpose

DS-EO is an engineering organization framework (roles, protocols, gates, workflow) that orchestrates AI agent sessions. Currently DS-EO depends on OpenClaw as its runtime harness. The **DSH Edition** migrates the primary runtime dependency from OpenClaw to DeepSeek Harness while preserving DS-EO's organizational architecture intact.

### Core Principle

> DS-EO governs *how* work gets done (roles, protocols, gates).  
> The runtime harness handles *what* agents execute (session lifecycle, model routing, tool dispatch).  
> The adapter layer is the only point of contact between DS-EO and any harness.

**DS-EO must not be redesigned to accommodate DSH.** DS-EO's governance architecture remains constant; only the runtime boundary changes.

---

## 3. Architecture: DSH Edition Scope

### Target Architecture

```
┌──────────────────────────────────────────────────┐
│              DS-EO (DSH Edition)                    │
│   Roles (CTO/PM/Implementer/Reviewer)             │
│   Governance (AGENTS.md, protocols/)               │
│   Workflow Engine (state machine, audit chain)      │
│   Task Management (gates, artifacts, reporting)     │
│   Model Registry (runtime-agnostic)                 │
└──────────────────────┬───────────────────────────┘
                       │ RuntimeAPI (adapter interface)
         ┌─────────────┴─────────────┐
         │                           │
  ┌──────────────┐          ┌─────────────────┐
  │ DSH Adapter  │          │ OpenClaw Legacy │
  │ (primary)    │          │ Adapter         │
  └──────┬───────┘          └────────┬────────┘
         │                          │
   DeepSeek Harness           OpenClaw (subprocess CLI)
         │                          │
     Ollama/Llama               Ollama (local)
```

### What DS-EO Retains (unchanged core)

| Component | Location | Notes |
|-----------|----------|-------|
| Role definitions (CTO, PM, Implementer, Reviewer) | `agents/` | Prompts unchanged; model assignments may shift later |
| Governance rules | `AGENTS.md` | All gate protocols, compaction recovery, source inspection — unchanged |
| Protocol documents | `protocols/` | Gate G0–G4, review, handoff, implementation — unchanged |
| Templates | `templates/` | TASK_COMPLETION_AUDIT, CTO_APPROVAL, REVIEW_REPORT — unchanged format |
| Workflow state machine | `ds_eo_openclaw/workflow/` (package name TBD) | State transitions unchanged; runtime calls abstracted behind adapter |
| Audit hash chain | `ds_eo_openclaw/session_health/audit.py` | Integrity verification unchanged |
| Failure/stall/escalation handling | `ds_eo_openclaw/workflow/` | Policy-driven, not harness-dependent |
| Execution strategy (hardware-aware) | `ds_eo_openclaw/dispatcher/execution_strategy/` | Model routing adapted via adapter, strategy unchanged |

### What is Replaced by the Adapter Layer

| Dependency (from RUNTIME_ADAPTER_DESIGN.md) | Current coupling | DSH Edition change |
|---------------------------------------------|-----------------|-------------------|
| **A1** — OpenClawAPI (compaction, archive, close) | Direct import in `discoverer.py`/`executor.py` | `RuntimeAdapter.compact()`, `.archive()` |
| **A2** — release_manager subprocess | `subprocess.run(...)` calls | Adapter-mediated via `run_task()` |
| **A3** — Session discovery (OpenClawAPI) | `discoverer.py:18` imports OpenClawAPI | `RuntimeAdapter.status()` replaces direct API call |
| **A4** — Hardcoded `~/.openclaw/notifications/` | `executor.py:200` absolute path | Runtime-agnostic notification config |
| **A5** — Model registry (ollama/*) | Hardcoded ollama in `cap_assessor.py` | Runtime-agnostic model list, resolved by adapter |
| **A6** — `sessions_spawn()` | Core dispatcher primitive | Replaced by DSH session dispatch via adapter |
| **A7** — Slash-command bindings | `dispatch/session_dispatch/`, `entry_points.yaml` | DSH hooks replace; OpenClaw bindings retired |
| **A8** — Tool policy | `supervisor.py` OpenClaw-specific | Adapter-mediated tool policy gate |
| **A9** — ollama capability probes | `capability_assessor.py` | Runtime-agnostic model info via adapter |
| **A10** — `~/.openclaw/ds-eo/projects.yaml` | 5 refs in `project_resolver/` | Runtime-agnostic config resolution |
| **A11** — Agent/model constants in docs | AGENTS.md, PROTOCOL.md, etc. | Config-layer adaptation only |

### What is Explicitly Out of Scope for the Migration

| Item | Rationale |
|------|-----------|
| Redesigning DS-EO roles or governance | DS-EO governance is the value; runtime is a detail |
| Building a new agent model (CTO/PM/etc. replacement) | Models are configuration, not architecture |
| Rewriting AGENTS.md or protocol documents | Governance rules remain identical |
| Implementing Phase 1+ adapter code | Deferred to TASK_DS_EO_DSH_002 onward |
| Migrating all existing OpenClaw tool bindings | Only migration-relevant tools; legacy tools stay behind OpenClaw adapter |
| Production deployment or CI/CD changes | Out of scope for the migration itself |
| Database, configuration schema, or persistence layer changes | Not affected by runtime swap |

---

## 4. Repository and Branch Strategy

### Repository

- **Canonical repo:** `github.com/Deepsim-AI/DS-EO` (unchanged)
- **No new repository.** DSH Edition develops within the existing DS-EO codebase.

### Branch Model

```
main
 └── dsh-migration          ← Working branch for all DSH phases
      ├── Phase 0: adapter interface + DshRuntimeAdapter
      ├── Phase 1: OpenClaw adapter (thinning)
      ├── Phase 2: model registry swap (D1)
      ├── Phase 3: bindings replacement (D2)
      ├── Phase 4: discovery swap (A3)
      └── Phase 5+: smoke tests + go-live
```

### Branch Convention

- **`main`:** Current production DS-EO OpenClaw Edition — no changes from DSH work.
- **`dsh-migration`:** All DSH migration development. This branch is the integration point for all TASK_DS_EO_DSH_00N tasks.
- Branches created under `dsh-migration/phase-N-*` are temporary work branches, merged back into `dsh-migration` upon CTO approval of each phase.

### Branching Strategy per Task

| Phase | Branch Name | Merge Target | Trigger |
|-------|-------------|--------------|---------|
| Phase 0 (adapter) | `dsh-migration/phase-0-adapter` | `dsh-migration` | After TASK_DS_EO_DSH_003 G4 |
| Phase 1 (OpenClaw thinning) | `dsh-migration/phase-1-thin` | `dsh-migration` | After TASK_DS_EO_DSH_004 G4 |
| Phase 2+ (D1/D2 swaps) | `dsh-migration/phase-N-*` | `dsh-migration` | Per-phase CTO approval |

### Commit Discipline

- **PM commits only:** After G5 closure, PM commits approved work. Implementer does not commit independently.
- **Post-G4 only:** All commits occur after full gate chain (G0→G1→G2→G3→G4→G5).
- **Remote push:** Only after explicit user confirmation of target repository and branch.

---

## 5. Migration Phases (Defined in RUNTIME_ADAPTER_DESIGN.md)

### Phase 0 — Foundation: Runtime Adapter Interface + DSH Adapter

**What:** Create `ds_eo/adapter/` package with `RuntimeAPI` interface, `DshRuntimeAdapter` implementation, and stub `OpenClawRuntimeAdapter`. No behavior change.

**Scope:** New files only. DS-EO core is unchanged because no component yet uses the new interface.

**Key files to create:**
- `ds_eo/adapter/__init__.py` — RuntimeAPI protocol/interface definition
- `ds_eo/adapter/dsh_adapter.py` — DshRuntimeAdapter (primary, against DSH)
- `ds_eo/adapter/openclaw_adapter.py` — OpenClawRuntimeAdapter (thin wrapper around existing OpenClawAPI)
- `ds_eo/runtime_factory.py` — Factory to resolve adapter by config

**Acceptance Criteria:**
- [ ] RuntimeAPI interface defined with all 10 methods from design doc (spawn_session, submit_task, run_tools, compact, archive, status, register_binding, model_info, available_models, run_task)
- [ ] DshRuntimeAdapter stubbed to DSH interfaces (no implementation depth required yet — just structure and type signatures)
- [ ] OpenClawRuntimeAdapter wraps existing OpenClawAPI with adapter interface compliance
- [ ] No code in `ds_eo/` core imports from `ds_eo/adapter/` or changes behavior
- [ ] Adapter package passes existing test suite (0 regressions)

### Phase 1 — OpenClaw Adapter Thinning

**What:** Move existing `OpenClawAPI` + subprocess calls into `OpenClawRuntimeAdapter`. Thin the interface. Replace direct OpenClawAPI imports in `discoverer.py` and `executor.py` with adapter pattern.

**Scope:** Refactor existing code behind adapter interface. No behavioral changes.

**Acceptance Criteria:**
- [ ] All 12 locations referencing `OpenClawAPI` or `openclaw_api` refactored to use RuntimeAdapter
- [ ] discoverer.py uses adapter, not direct OpenClaw import
- [ ] executor.py uses adapter, not direct OpenClaw import  
- [ ] Existing tests pass (no behavioral regression)
- [ ] Adapter pattern verified by at least one integration test exercising both adapters

### Phase 2 — Model Registry Swap (D1)

**What:** Replace hardcoded `ollama/*` model references with runtime-agnostic model list resolved through adapter. The manifest's model registry routes through the adapter rather than embedding provider-specific logic.

**Scope:** Configuration-layer change. `ds_eo_manifest.yaml` model entries remain structurally identical; resolution layer changes.

**Acceptance Criteria:**
- [ ] Model selection no longer hardcodes `ollama list/show` calls
- [ ] Runtime-agnostic model list in manifest resolved by adapter at runtime
- [ ] Capability assessment uses adapter's `model_info()` / `available_models()`
- [ ] No behavioral difference on OpenClaw path (backwards compatible)

### Phase 3 — Bindings Replacement (D2)

**What:** Replace A7 slash-command bindings (`/evo.session`, `/eo.session.list`) with DSH hooks. Retire OpenClaw-specific entry_points.yaml bindings.

**Scope:** Configuration and glue code only. Not runtime-dispatched behavior.

**Acceptance Criteria:**
- [ ] All OpenClaw slash bindings replaced with DSH hooks in config layer
- [ ] `entry_points.yaml` references to OpenClaw bindings archived/marked legacy
- [ ] DSH hooks produce equivalent command routing behavior
- [ ] Existing session management tools still callable

### Phase 4 — Discovery Swap (A3)

**What:** Replace `discoverer.py`'s direct OpenClAPI call with adapter's `status()` method pointing to DSH session registry.

**Scope:** Single-file refactor of discoverer.py. Highest-leverage single swap.

**Acceptance Criteria:**
- [ ] discoverer.py uses RuntimeAdapter.status() exclusively
- [ ] Session discovery works via DSH registry (not OpenClaw API)
- [ ] Health monitoring, idle detection, and session classification unchanged
- [ ] Tests verify discovery path against both adapter implementations

### Phase 5+ — Smoke Tests + Go-Live

**What:** Re-run existing test suite (631 cases) against DSH adapter. Run reliability comparison per RUNTIME_ADAPTER_DESIGN.md Deliverable E. Flip default from OpenClaw to DSH.

**Acceptance Criteria:**
- [ ] All 631 tests pass against DSH adapter (same as on OpenClaw)
- [ ] Reliability comparison matrix completed (Deliverable E metrics)
- [ ] Default runtime in `ds_eo_manifest.yaml` switched to DSH
- [ ] OpenClaw adapter retained as legacy backend for backward compatibility

---

## 6. Task Sequence

```
TASK_DS_EO_DSH_001  →  Project Bootstrap + Migration Definition (this task, PM scope)
    ↓
TASK_DS_EO_DSH_002  →  Technical Architecture and Implementation Plan (CTO scope)
    ↓
TASK_DS_EO_DSH_003  →  Phase 0: Adapter Interface + DSH Adapter (Implementer)
    ↓
TASK_DS_EO_DSH_004  →  Phase 1: OpenClaw Adapter Thinning (Implementer)
    ↓
TASK_DS_EO_DSH_005  →  Phase 2: Model Registry Swap (D1) (Implementer)
    ↓
TASK_DS_EO_DSH_006  →  Phase 3: Bindings Replacement (D2) (Implementer)  
    ↓
TASK_DS_EO_DSH_007  →  Phase 4: Discovery Swap (A3) (Implementer)
    ↓
TASK_DS_EO_DSH_008  →  Smoke Tests + Reliability Comparison + Go-Live (Implementer + Reviewer)
```

### Cross-Task Governance Rules

1. **Each task follows the full gate chain** (G0→G1→G2→G3→G4→G5). No shortcuts.
2. **Reviewer verifies before CTO approves.** Each phase's implementation must pass review before G4.
3. **PM commits only after G5 closure.** Git operations are PM-only, post-G4.
4. **Each phase targets one merge into `dsh-migration`.** No parallel integration.
5. **Phase 2+ acceptance criteria explicitly reference deliverables from Phase 0.** Phases are cumulative.

---

## 7. Artifact Organization

### Project Root: `/home/deepsim/ds_eo_dsh/`

```
ds_eo_dsh/                          ← DSH Edition project root (working directory)
├── README.md                       ← Project overview, quick start, migration status
├── PROJECT_STATUS.md               ← Phase-level progress tracker (updated post-G4 each phase)
├── CHANGELOG.md                    ← Migration changelog
├── RUNTIME_ADAPTER_DESIGN.md       ← Preserved: from ds_eo_openclaw_test/ (design reference)
├── INSPECTION_REPORT.md            ← Preserved: from ds_eo_dsh/ (inspection results)
├── tests/                          ← DSH Edition test suite (extends existing tests)
│   ├── test_adapter/               ← Adapter-specific tests
│   └── ...                         ← Existing test structure migrated
├── ds_eo_openclaw/                 ← DS-EO core package (refactored to use adapter)
│   ├── __init__.py
│   ├── adapter/                    ← Phase 0: Runtime API + both adapters
│   │   ├── __init__.py             ← RuntimeAPI interface
│   │   ├── dsh_adapter.py          ← DshRuntimeAdapter
│   │   └── openclaw_adapter.py     ← OpenClawRuntimeAdapter (thin wrapper)
│   ├── workflow/                   ← Core workflow (unchanged governance)
│   ├── session_health/             ← Health monitoring (adapter-dependent)
│   ├── release_manager/            ← Release management (adapter-dependent)
│   └── dispatcher/                 ← Dispatcher (adapter-dependent)
├── ds_eo_manifest.yaml             ← DS-EO manifest (model registry → adapter route)
├── config-templates/               ← DSH-compatible configuration templates
├── .github/workflows/              ← CI: release.yml updated for DSH path
```

### Task Directories

Task artifacts remain in `/home/deepsim/ds_eo_openclaw/docs/development/reports/` as per DS-EO governance protocol. This workspace is the canonical task artifact repository — it is not moved or copied.

```
/home/deepsim/ds_eo_openclaw/docs/development/reports/
├── TASK_DS_EO_DSH_001_PLAN/       ← This task (bootstrap + migration definition)
│   ├── CTO_PLAN.md
│   ├── TASK_COMPLETION_AUDIT.md
│   └── PROJECT_STATUS.md           ← Phase tracker for TASK 001 scope
├── TASK_DS_EO_DSH_002_*           ← Future: CTO tech plan
├── TASK_DS_EO_DSH_003_*           ← Future: Phase 0 implementation
└── ...
```

---

## 8. Isolation Rules (Non-Negotiable)

| Rule | Scope | Rationale |
|------|-------|-----------|
| **R1:** Do NOT access or modify real `~/.openclaw` environment | All agents, all phases | Security; prevents session interference during migration |
| **R2:** Do NOT create/deleted/compact/archive/modify real OpenClaw sessions | All agents, all phases | Same — operational boundary |
| **R3:** Do NOT modify the production DS-EO repository (`main` branch) | All implementation tasks | Production safety; DSH work is on `dsh-migration` branch |
| **R4:** Do NOT blind-copy `ds_eo_openclaw_test` workspace | Implementation | Contains experimental state, host-specific config, session artifacts |
| **R5:** Preserve existing DS-EO governance (AGENTS.md, protocols, templates) unchanged | All phases | DS-EO architecture is the value; runtime swap doesn't change it |
| **R6:** Each phase's implementation must pass the full 631-test suite | CTO G4 gate, PM G5 closure | No behavioral regression allowed |
| **R7:** OpenClaw adapter retained as legacy backend | Post-Phase 0 onward | Backward compatibility; not removed until explicitly decided |

---

## 9. Test Strategy

### Pre-Migration Baseline (Current)

| Suite | Cases | Passing | Notes |
|-------|-------|---------|-------|
| `tests/` (main) | 570 | 568/570 | 2 failures due to read-only host (~/.openclaw), not logic faults |
| `test/execution_strategy/` | 53 | 53/53 | Self-contained, host-independent |
| `tests/test_installation_flow.sh` | 10 | 10/10 | Smoke test |
| **Total** | **633** | **631 passing** | Baseline to maintain |

### Per-Phase Test Requirements

Each phase's CTO G4 gate requires:
- [ ] All pre-existing tests pass (same 570 + 53 + 10 = 633 cases)
- [ ] No new test regressions introduced by the phase
- [ ] Phase-specific integration tests for the adapter boundary (new tests)
- [ ] `TASK_COMPLETION_AUDIT.md` gate status reflects results

### Post-Migration Verification (Phase 5+)

Run per RUNTIME_ADAPTER_DESIGN.md Deliverable E:

| Metric | Method | Target |
|--------|--------|--------|
| Task completion rate % | Identical task set on DSH vs OpenClaw adapter | ≥90% (not < current baseline) |
| Tool execution success % | Count `run_tools` reliability per session | ≥95% |
| Run errors (HTTP 500) | Count against OpenClaw path only | Track, no target yet |
| Idleness events | Count status() idle reports | Track |
| Avg/p95 latency | Per-turn measurement across runs | DSH ≥ OpenClaw on local hardware |
| Recovery success % | Injected failure + resume test | Same as OpenClaw baseline |
| Context handling | Compaction error frequency comparison | ≤ OpenClaw baseline |
| Memory peak | RAM tracking during execution | Track for both paths |
| Long-running stability | 100+ task run, drift measurement | No session leaks |

---

## 10. Acceptance Criteria Summary

### G2 (Implementation Ready) — All Must Pass

- [ ] DSH Edition scope clearly defined and documented (this CTO_PLAN.md + PROJECT_STATUS.md)
- [ ] Migration phases defined with explicit acceptance criteria
- [ ] Repository/branch strategy established (`dsh-migration`)
- [ ] Artifact organization structure finalized
- [ ] Isolation rules enumerated and enforced via gate checks
- [ ] Test strategy defined per above section 9
- [ ] Task sequence locked (TASK_DS_EO_DSH_002 through _008)

### G4 (CTO Approval Ready) — For Subsequent Tasks Only

- [ ] Implementation matches this plan exactly (no scope creep)
- [ ] All tests pass per test strategy
- [ ] Reviewer confirms specification compliance
- [ ] No behavioral regression on OpenClaw path

### G5 (PM Closure Ready)

- [ ] CTO_APPROVAL.md exists with gate status
- [ ] REVIEW_REPORT.md exists
- [ ] Artifact integrity verified (metadata, structure)
- [ ] PROJECT_STATUS.md updated in ds_eo_dsh
- [ ] CHANGELOG.md updated
- [ ] Work committed and pushed to `dsh-migration` branch
- [ ] User confirms remote push target

---

## 11. Risks

| Risk | Mitigation |
|------|-----------|
| Scope creep: phase implementations absorbing DS-EO governance changes | Gate checks enforce R5 (governance unchanged); CTO rejects scope creep at G4 |
| Adapter adds indirection that masks bugs | Per-phase integration tests exercise both adapters; DSH adapter gets higher test coverage |
| OpenClaw path regresses during refactoring | All 633 tests must pass before any phase reaches G4; rollback available per branch model |
| DSH interface changes mid-migration | TASK_DS_EO_DSH_002 (next task) will validate DSH interfaces against adapter requirements; if incompatible, scope for Phase 0 adjusts |
| Read-only host constraint prevents in-place validation | Migration code reviewed on production-capable host before merge to `dsh-migration` |

---

## 12. What This Task Delivers (Deliverables)

| # | Deliverable | Location | Status |
|---|------------|----------|--------|
| D1 | CTO_PLAN.md (this document) | `reports/TASK_DS_EO_DSH_001_PLAN/` | ✅ PRODUCED |
| D2 | TASK_COMPLETION_AUDIT.md | `reports/TASK_DS_EO_DSH_001_PLAN/` | ✅ PRODUCED |
| D3 | PROJECT_STATUS.md (project-level tracker) | `/home/deepsim/ds_eo_dsh/` | ✅ TO BE WRITTEN |
| D4 | Migration boundary definition | This CTO_PLAN.md, §3 | ✅ PRODUCED |
| D5 | Task sequence | This CTO_PLAN.md, §6 | ✅ PRODUCED |
| D6 | Repository/branch strategy | This CTO_PLAN.md, §4 | ✅ PRODUCED |
| D7 | Isolation rules | This CTO_PLAN.md, §8 | ✅ PRODUCED |
| D8 | Test strategy | This CTO_PLAN.md, §9 | ✅ PRODUCED |

---

## 13. Pending Decisions (Require User Input)

1. **Should I `git init` the `/home/deepsim/ds_eo_dsh/` directory?**  
   User decided NOT to create a new repo — but does DSH need its own git init, or will it be developed as a working tree that is later added to the DS-EO repo? Clarification needed.

2. **Next task: TASK_DS_EO_DSH_002** — Should this task be defined immediately (CTO planning) or deferred until user approves CTO_PLAN.md and signals readiness?

3. **DSH Edition name** — Is "DS-EO DSH Edition" the final naming, or should TASK_DS_EO_DSH_002 define a project name/title?
