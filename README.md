# DS-EO DSH Edition

**Deepsim Engineering Organization — DSH Edition**

A runtime-migrated engineering organization framework that transforms an AI agent platform (DeepSeek Harness) into a disciplined software engineering team. This edition is the DeepSeek Harness primary-runtime deployment of DS-EO, migrating the runtime layer from OpenClaw to DSH via a pluggable Runtime Adapter architecture.

---

## What Is DS-EO?

DS-EO provides:

- **Engineering roles** with clear responsibilities and tool policies
- **Dispatcher/Workflow Engine** — PM-driven programmatic task orchestration
  across G0–G4 gates via session dispatch with isolated contexts
- **Gateway bindings** — minimal entry points that route to the PM
- **Communication protocols** for agent-to-agent messaging
- **Development workflows** with formal approval gates
- **Review processes** with scoring rubrics
- **Task lifecycle management** from planning through delivery
- **Persistent state** per-task (dispatcher_state + dispatch_log)
  that survives gateway restarts and enables audit trails
- **Portable configuration** that installs into any agent platform

## Architecture: Two-Layer Model

DS-EO separates the **engineering organization** (who builds) from the **runtime harness** (what agents run on):

```
User Request (/eo task → PM)
    │
    ▼
┌─────────────────────┐     ┌───────────────────────────┐
│  Dispatcher Engine   │ ←── │ Gateway Bindings (entry)  │
│  G0 intake + G1–G4  │     │ /eo.task → PM             │
│  sessions_dispatch() │     │ /eo.approve → CTO         │
│  state persistence  │     │ /eo.review → Reviewer     │
└──────────┬──────────┘     └───────────────────────────┘
           │
    Agent Spawns (isolated sessions)
           ▼
┌─────────────────────┐
│  PM ← CTO →         │
│  Implementer ↔      │
│  Reviewer           │
└─────────────────────┘
    │
    ▼
Runtime Adapter Layer  ←── the migration boundary
├── DSH Runtime Adapter (primary)
└── OpenClaw Legacy Adapter (backward-compatible backend)
    │
    ▼
Agent Execution Platform (DeepSeek Harness / Ollama)
```

### Migration Summary

DS-EO was originally built for OpenClaw as the primary runtime. The **DSH Edition** migrates the runtime layer to DeepSeek Harness while preserving DS-EO's organizational architecture intact:

| Component | DS-EO Original (OpenClaw) | DSH Edition |
|-----------|--------------------------|-------------|
| Governance (AGENTS.md, protocols, templates) | Unchanged | Unchanged |
| Roles (CTO, PM, Implementer, Reviewer) | Unchanged | Unchanged |
| Workflow Engine (state machine, audit chain) | Unchanged | Unchanged |
| Runtime Harness | OpenClaw | **DeepSeek Harness** |
| Adapter Boundary | Not present | **New: `ds_eo/adapter/` package** |

## Quick Start

### Prerequisites

- DeepSeek Harness installed and running
- Access to configuration (`openclaw.json` or equivalent)
- Git (optional, for version control)

### Installation

```bash
# Clone this repository
git clone git@github.com:Deepsim-AI/DS-EO.git ds-eo-dsh
cd ds-eo-dsh

# Run the interactive installer
bash scripts/install.sh
```

The installer will:
1. Back up your existing config
2. Prompt for model names (or use DSH-appropriate defaults)
3. Merge agent configurations into config
4. Deploy protocol files to appropriate locations

---

### Changing Agent Models (Post-Install)

Models are defined in `ds_eo_manifest.yaml` and `openclaw.json`. Compare your config against the manifest to verify consistency.

**Quick reference — current defaults:**

| Agent | Config Field | Default Model |
|-------|-------------|---------------|
| CTO / Architect 🏗️ | `"id": "cto"` → `"model"` | `ollama/qwen3.6:35b` |
| Code Implementer 💻 | `"id": "implementer"` → `"model"` | `ollama/qwen3.8:27b` |
| Senior Code Reviewer 🔍 | `"id": "reviewer"` → `"model"` | `ollama/laguna-xs-2.1:q4_K_M` |
| Project Manager 📋 | `"id": "pm"` → `"model"` | `ollama/ornith-1.5:35b` |

## Runtime Migration Phases

The DSH Edition evolves through a phased migration of runtime coupling behind the adapter boundary:

| Phase | Task | Status | Description |
|-------|------|--------|-------------|
| 0 | TASK_DS_EO_DSH_003 | ✅ Done | Adapter interface + DSH stub + OpenClaw legacy adapter |
| 1 | TASK_DS_EO_DSH_004 | ✅ Done | OpenClaw adapter thinning (session_health → adapter) |
| 2 | TASK_DS_EO_DSH_005 | Pending | Model registry swap (remove hardcoded ollama refs) |
| 3 | TASK_DS_EO_DSH_006 | Pending | Bindings replacement (slash commands → DSH hooks) |
| 4 | TASK_DS_EO_DSH_007 | Pending | Discovery swap (DSH session registry) |
| 5+ | TASK_DS_EO_DSH_008 | Pending | Smoke tests + reliability comparison + go-live |

See `PROJECT_STATUS.md` for detailed tracking.

## Repository Structure

```
ds-eo-dsh/                          ← DSH Edition root
├── README.md                       ← This file
├── ARCHITECTURE.md                 ← Core concepts and design decisions
├── INSTALLATION.md                 ← Step-by-step installation guide
├── CHANGELOG.md                    ← Version history
├── ds_eo_manifest.yaml             ← Package manifest (source of truth)
├── PROJECT_STATUS.md               ← DSH Edition migration tracker
│
├── ds_eo_openclaw/                 ← Python package modules
│   ├── adapter/                    ← Phase 0: Runtime Adapter layer
│   │   ├── runtime_api.py          ← RuntimeAPI Protocol + data types
│   │   ├── dsh_adapter.py          ← DSH primary adapter (stubs)
│   │   ├── openclaw_adapter.py     ← OpenClaw legacy adapter (thin wrapper)
│   │   └── __init__.py             ← Package exports
│   ├── session_health/             ← Session discovery, classification, policy
│   ├── workflow/                   ← 11-state state machine + audit chain
│   ├── dispatcher/                 ← Dispatcher engine + registry
│   ├── intake/                     ← Task intake manager
│   ├── run_reliability/            ← Reconciliation layer
│   └── release_manager.py          ← Release operations
│
├── agents/                         ← Role definitions (portable prompts)
├── protocols/                      ← Engineering protocols
├── templates/                      ← Document templates
├── config-templates/               ← Reference configurations
├── scripts/                        ← Installation and management helpers
├── tests/                          ← Verification and compliance tests
├── test/                           ← Execution strategy unit tests
├── docs/reports/                   ← Task artifacts (gate chain)
├── examples/                       ← Usage examples
└── benchmarks/                     ← Benchmark suite
```

## Roles

| Role | Emoji | Description | Default Model |
|------|-------|-------------|---------------|
| CTO / Architect 🏗️ | 🏗️ | Architecture, planning, final approval authority | `ollama/qwen3.6:35b` |
| Code Implementer 💻 | 💻 | Execute approved plans, produce working code | `ollama/qwen3.8:27b` |
| Senior Code Reviewer 🔍 | 🔍 | Independent verification and quality assessment | `ollama/laguna-xs-2.1:q4_K_M` |
| Project Manager 📋 | 📋 | Process oversight — task lifecycle, status tracking, release management | `ollama/ornith-1.5:35b` |

## Development Workflow

### Canonical Flow (PM-driven programmatic orchestration)

```
/eo task → PM dispatches CTO (S0→S1)
    │
    ├── G1: User approves CTO_PLAN.md
    │   └── Dispatcher delegates to Implementer via sessions_dispatch()
    │       ├── Implementation complete → routes to Reviewer (S3)
    │       ├── Review approved → routes to CTO for G4 (S4)
    │       └── User approves → PM completes S5 (PM_CLOSED + cleanup)
    │
    └── Rejection loops: any gate can route work back to Implementer (S2)
```

### Routing Design Principle

**Gateway bindings expose only entry points — all workflow routing lives inside DS-EO.**

The dispatcher engine reads `workflow_defs/default.yaml` to determine phase transitions, authority requirements, and artifact prerequisites. No routing logic is embedded in gateway configuration.

Four formal approval gates ensure quality at every phase transition. See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Roadmap

- **v0.1** (completed): Extract, package, and install DS-EO OpenClaw Edition
- **v0.2** (completed): Protocol & governance consistency migration
- **v0.3** (completed): Automatic Mode — full workflow engine, audit trail, failure handling
- **v0.4** (completed): Dispatcher/Workflow Engine layer
- **v0.5** (completed): Task Intake Manager Layer
- **v0.6** (completed): Session Health and Lifecycle Management Layer
- **v0.8** (shipped): Complete Automatic Workflow Management System
- **DSH Migration Phases 2–5** (in progress)
- **v1.0** (planned): Platform abstraction layer for multi-platform editions

## License

MIT

Copyright (c) 2026 Deepsim Intelligence Technology Inc.


---

# Project Maintainer

**Dr. Shouke Wei (魏守科)**  
Founder, Deepsim Intelligence Technology Inc.

DS-EO DSH Edition is developed and maintained by the Deepsim AI Lab at Deepsim Intelligence Technology Inc.
---

*Built with DS-EO DSH Edition.*
