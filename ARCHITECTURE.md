# DS-EO Architecture — OpenClaw Edition

## Core Concepts

### Two-Layer Model

DS-EO operates on a fundamental separation between two layers:

| Layer | What It Is | Where It Lives |
|-------|-----------|----------------|
| **Engineering Organization** (build-time) | CTO, Implementer, Reviewer, PM — the team that develops software | OpenClaw agent configs + prompt files |
| **Runtime Product** (product-time) | CEO Agent, Research, Writer, etc. — what gets built | The deployed application |

**Critical rule**: Never conflate the two layers. The CTO is not a replacement for the CEO Agent. The engineering organization develops software; the runtime product runs at deployment time.

### Dispatcher / Workflow Engine Layer (v0.4)

The dispatcher is the single orchestration layer for all task routing:

```
Gateway Bindings (entry points only)
    │
    ├── /eo.task ──► PM  ──[G0_ENTRY]──► CTO (S1_PLANNING)
    ├── /eo.approve ──► CTO (G1 plan review)
    └── /eo.review ──► Reviewer (G3 review trigger)
    
PM Dispatcher Engine
    │  reads: workflow_defs/default.yaml + agents_list.json
    │  writes: docs/dispatchers/<TASK_ID>/dispatcher_state.json
    │  
    ├── G1_APPROVE ──► sessions_spawn(implementer, context="isolated")
    ├── G2_COMPLETE ──► sessions_spawn(reviewer, context="isolated")  
    ├── G3_APPROVE ──► sessions_spawn(cto, context="isolated")
    ├── G3_CHANGES ──► S2_IMPLEMENTATION (revision loop)
    ├── G4_APPROVE ──► S5_COMPLETE + PM_CLOSED
    └── G4_REJECT ──► S2_IMPLEMENTATION (deep rejection)

All internal routing is data-driven from YAML. No workflow logic in gateway config.
```

#### CTO / Architect 🏗️

- **Model**: Configurable (default: `ollama/qwen3.6:35b`)
- **Role**: Architecture review, task planning, final approval authority
- **Tool Policy**: `sessions_spawn`, `sessions_send` (delegation to Implementer), `exec`, `process`, read access; write only in task directories (behavioral boundary)
- **Key Responsibility**: Never modify source code directly — that is the Implementer's role. Delegates work via dispatcher engine.
- **Key Responsibility**: Never modify source code — that is the Implementer's role

#### Code Implementer 💻

- **Model**: Configurable (default: `ollama/ornith:35b`)
- **Role**: Execute approved plans with full file system access
- **Tool Policy**: Full repository access (`tools.allow`: group:fs, group:runtime, etc.)
- **Key Constraint**: Follow the CTO's plan exactly — no independent architectural decisions

#### Senior Code Reviewer 🔍

- **Model**: Configurable (default: `ollama/laguna-xs-2.1:q4_K_M`)
- **Role**: Independent quality verification
- **Tool Policy**: Can produce REVIEW_REPORT.md (`tools.allow`: group:fs, exec, process, write; `tools.deny`: edit, apply_patch)
- **Key Constraint**: May only write REVIEW_REPORT.md in the current task directory — never modify source code

#### Project Manager 📋

- **Model**: Configurable (default: `ollama/qwen3.6:35b`)
- **Role**: Process oversight — task lifecycle, status tracking, release management
- **Tool Policy**: `exec` (dispatcher invocation, file checks), `write` (designated PM paths), `sessions_list`, `session_status`, `memory_search`, `memory_get`, `group:fs` for state inspection
- **Key Constraint**: No source code modifications; no independent architectural decisions. Uses dispatcher engine for task orchestration per [PM_DISPATCHER_SKILL.md](dispatcher/PM_DISPATCHER_SKILL.md)

### Development Workflow

All implementation work follows this four-phase sequence with formal gates:

```
Phase 1 (Planning) ──G1──→ Phase 2 (Implementation) ──G2──→ Phase 3 (Review) ──G3──→ Phase 4 (Approval)
     │                           │                              │                            │
   CTO                          Implementer                    Reviewer                     CTO
```

| Gate | From → To | Authority | Decision Type |
|------|-----------|-----------|---------------|
| **G1** | Planning → Implementation | User approves CTO's plan | Approve / Request revision |
| **G2** | Implementation → Review | Implementer self-declares complete + CTO confirms | Complete? |
| **G3** | Review → Approval | Reviewer recommends pass/fail | Passes? |
| **G4** | Approval → Complete | CTO final decision | Approve / Reject |

### Artifact-Based Handoff Protocol

Every task gets a dedicated directory under `docs/development/reports/TASK_<id>/`:

```
TASK_<YYYYMMDD>_<NNN>/
├── CTO_PLAN.md              # Architecture analysis + plan (CTO produces)
├── IMPLEMENTATION_REPORT.md  # Changes, tests, decisions (Implementer produces)
├── REVIEW_REPORT.md          # Findings and recommendation (produced by Reviewer)
└── CTO_APPROVAL.md           # Final approve/reject with rationale (CTO produces)
```

**Naming convention**: `TASK_<YYYYMMDD>_<NNN>` where NNN resets daily starting at 001. The CTO exclusively owns task creation and numbering.

### Protocol Hierarchy

Protocols exist in three layers:

```
~/.openclaw/protocols/*.md     ← Global standards (authoritative)
                                    ↑
                              DS-EO package defines these as source of truth
                                    ↓
<project>/docs/development/protocols/*.md  ← Project-level adaptations (optional)

dispatcher/binding_defs/          ← Gateway entry-point bindings (YAML, applied to openclaw.json)
workflow_defs/default.yaml        ← Data-driven G0-G4 gate machine definition (dispatcher engine reads this)


DS-EO defines its own authoritative protocol copies in the package. Installation deploys them to both global (`~/.openclaw/protocols/`) and per-project locations. The global versions serve as the source of truth for all projects using DS-EO.

### Protocol Categories

| Category | Protocols | Purpose |
|----------|-----------|---------|
| Governance | `approval_protocol.md`, `review_protocol.md`, `GATE_AUTHORITY_MATRIX.md` | Gates, scoring, decision authority, gate governance |
| Communication | `communication_protocol.md` | Message formats and conventions |
| Workflow | `delegation_protocol.md`, `handoff_protocol.md`, `completion_protocol.md` | Task lifecycle management |

## Configuration Architecture

### OpenClaw Agent Loading

OpenClaw loads agents via `openclaw.json` → `agents.list[]`. Each agent is a JSON object:

```json
{
  "id": "<agent_id>",
  "name": "<Display Name>",
  "identity": { "emoji": "<char>", "name": "<short>" },
  "model": "<model_name>",
  "workspace": "<path>",
  "tools": {
    "allow": ["group:fs", ...],
    "deny": [...],
    "profile": "<profile_name>"
  }
}
```

DS-EO's installation generates these entries and safely merges them into the host's `openclaw.json`.

### Merge Safety Guarantees

The configuration merge is designed to be non-destructive:

1. **Only `agents.list[]` and optionally `agents.defaults.model.primary` are modified**
2. Gateway, plugins, skills, channels sections are never touched
3. Existing non-DS-EO agent entries are preserved (unless same ID — then replaced)
4. Atomic write with post-merge JSON validation
5. Automatic rollback on verification failure

### Model Placeholders

The package uses placeholders that the installer replaces:

| Placeholder | Default Value | Description |
|-------------|--------------|-------------|
| `<MODEL_CTO>` | `ollama/qwen3.6:35b` | CTO model |
| `<MODEL_IMPLEMENTER>` | `ollama/ornith:35b` | Implementer model |
| `<MODEL_REVIEWER>` | `ollama/laguna-xs-2.1:q4_K_M` | Reviewer model |
| `<WORKSPACE_PATH>` | User-specified | Project workspace path |

## Design Decisions

### Why YAML Manifest?

The package manifest (`ds_eo_manifest.yaml`) serves as the single source of truth for what DS-EO is and contains. It enables:
- Automated validation (is installation complete?)
- Human-readable inspection
- Structured metadata about roles, protocols, templates, and installation steps

### Why Separate Scripts from Tests?

Installation scripts (`scripts/`) handle the deployment workflow. Verification tests (`tests/`) validate correctness independently. This separation means:
- The same package can be tested without installing
- CI pipelines can run verification without touching user configs
- Rollback logic is in install scripts; validation logic is in test files

### Why No OpenClaw Source Modification?

DS-EO installs by merging configuration and deploying files — it never modifies OpenClaw's source code. This means:
- Uninstallation is clean (just remove the merged entries)
- OpenClaw updates don't break DS-EO installations
- The package is portable across OpenClaw versions (within compatibility range)

## Future Architecture

### v0.3 — Automatic Mode (completed)

Full workflow engine with automatic mode support, audit trail, user-facing mode selector, failure/stall handling, and slash command skill. See [CHANGELOG.md](CHANGELOG.md) for details on all 6 implementation phases.

### v0.4 — Dispatcher/Workflow Engine Layer (in-progress)

PM-driven programmatic orchestration replacing direct CTO dispatch:
- `dispatcher/registry.py` — Agent registry with SHA256 integrity checksums
- `dispatcher/engine.py` — G0-G4 gate machine (data-driven from YAML workflow definitions)
- `dispatcher/state_manager.py` — Persistent per-task state, atomic writes, audit log appender
- `dispatcher/dispatch.py` — Unified API for PM task lifecycle management
- `dispatcher/session_dispatch/` — sessions_spawn wrapper for isolated agent handoffs
- Gateway bindings expose entry points only; all internal routing lives in dispatcher (design constraint)
- PM tool policy expanded: exec, write, sessions_list, memory access
- CTO tool policy expanded: sessions_spawn, sessions_send for delegation

### v1.0 — Platform Abstraction

### v1.0 — Platform Abstraction

Extract platform-independent concepts into a `ds-eo-core/` layer with adapter patterns:

```
ds-eo-core/           ← Platform-independent roles, protocols, templates
    │
adapters/             ← Platform-specific implementations
├── openclaw/         ← Current edition (this package)
├── claude/           ← Future
├── codex/            ← Future
└── gemini/           ← Future
```

### v2.0+ — Ecosystem

Additional editions for different AI agent platforms, sharing the same core framework.
