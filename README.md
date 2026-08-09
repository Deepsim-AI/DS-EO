# DS-EO OpenClaw Edition

**DeepSim Engineering Organization — OpenClaw Edition**

A reusable engineering organization framework that transforms an AI agent platform into a disciplined software engineering team. This is the first platform-specific edition (OpenClaw).

---

## What Is DS-EO?

DS-EO provides:

- **Engineering roles** with clear responsibilities and tool policies
- **Dispatcher/Workflow Engine** — PM-driven programmatic task orchestration
  across G0–G4 gates via `sessions_spawn()` with isolated contexts
- **Gateway bindings** — minimal entry points (`/eo.task`, `/eo.approve`,
  `/eo.review`) that route to the PM; no workflow logic in gateway config
- **Communication protocols** for agent-to-agent messaging
- **Development workflows** with formal approval gates
- **Review processes** with scoring rubrics
- **Task lifecycle management** from planning through delivery
- **Persistent state** per-task (dispatcher_state.json + dispatch_log.jsonl)
  that survives gateway restarts and enables audit trails
- **Portable configuration** that installs into any OpenClaw host

## Architecture: Two-Layer Model

DS-EO separates the **engineering organization** (who builds) from the **runtime product** (what is built):

```
User Request (/eo task → PM)
    │
    ▼
┌─────────────────────┐     ┌───────────────────────────┐
│  Dispatcher Engine   │ ←── │ Gateway Bindings (entry)  │
│  /eo.task, G0–G4    │     │ /eo.task → PM             │
│  sessions_spawn()   │     │ /eo.approve → CTO         │
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
Runtime Product (CEO Agent, Research, Writer, etc.)
```

The engineering organization is portable across platforms. The runtime product is project-specific. Never conflate the two.

## Quick Start

### Prerequisites

- OpenClaw installed and running (`2026.7.1` or later)
- Access to `~/.openclaw/openclaw.json`
- Git (optional, for version control)

### Installation

```bash
# Clone this repository
git clone git@github.com:Deepsim-AI/DS-EO.git ds-eo-openclaw
cd ds-eo-openclaw

# Run the interactive installer
bash scripts/install.sh
```

The installer will:
1. Back up your existing `openclaw.json`
2. Prompt you for model names (or use defaults)
3. Merge agent configurations into `openclaw.json`
4. Deploy protocol files to global and project locations

---

### Windows

```powershell
# Clone this repository
git clone git@github.com:Deepsim-AI/DS-EO.git ds-eo-openclaw
cd ds-eo-openclaw

# Run the interactive installer (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

Prerequisites for Windows:
- PowerShell 5.1+ (Windows 10/11 includes this by default)
- Python 3.8+ (used by the installer for JSON/YAML processing)
- OpenClaw installed and running (`2026.7.1` or later)
- Git (for repository management)

For best results, install WSL2 and use `bash scripts/install.sh` within the Linux environment for full compatibility.

## Repository Structure

```
ds-eo-openclaw/
├── README.md                    # This file
├── ARCHITECTURE.md              # Core concepts and design decisions
├── INSTALLATION.md              # Step-by-step installation guide
├── CHANGELOG.md                 # Version history
├── ds_eo_manifest.yaml          # Package manifest (source of truth)
│
├── agents/                      # Role definitions (portable prompts)
│   ├── cto.md                   # CTO / Architect prompt
│   ├── implementer.md           # Code Implementer prompt
│   ├── reviewer.md              # Senior Code Reviewer prompt
│   └── pm.md                   # Project Manager prompt
│
├── protocols/                   # Engineering protocols (core rules)
│   ├── README.md                # Protocol hierarchy guide
│   ├── approval_protocol.md     # Gate definitions, rejection handling
│   ├── communication_protocol.md# Message formats and conventions
│   ├── completion_protocol.md   # Per-role completion checklists
│   ├── delegation_protocol.md   # Task creation and assignment
│   ├── handoff_protocol.md      # Phase transition requirements
│   ├── review_protocol.md       # Review criteria and scoring rubric
│   └── GATE_AUTHORITY_MATRIX.md # Single source of truth for gate governance
│
├── templates/                   # Reusable document templates
│   ├── task.md                  # TASK directory structure template
│   ├── report_template.md       # Implementation report format
│   ├── review_report_template.md# Review report format
│   ├── spec_template.md         # Specification document format
│   └── cto_approval_template.md # CTO approval memo format
│
├── config-templates/            # Reference configurations
│   ├── example_openclaw_config.json  # Example agents.list[] entries
│   └── model_placeholders.txt       # Placeholder conventions
│
├── scripts/                     # Installation and management helpers
│   ├── install.sh                 # Main installer (Linux/macOS/WSL2)
│   ├── install.ps1                # Main installer (Windows/PowerShell)
│   ├── backup_openclaw_config.sh  # Pre-install backup
│   ├── conflict_check.sh          # Pre-install conflict detection
│   ├── generate_openclaw_config.sh# Generate and merge agent config
│   ├── deploy_protocols.sh        # Protocol deployment
│   ├── deploy_agents.sh           # Prompt file deployment
│   └── verify_installation.sh     # Post-install verification
│
├── tests/                       # Verification and compliance tests
│   ├── test_manifest_schema.py      # Manifest schema validation
│   ├── test_protocol_extraction.py  # Protocol completeness check
│   ├── test_template_completeness.py# Template section checks
│   ├── test_config_merge_safety.py  # Config merge safety
│   └── test_installation_flow.sh    # End-to-end smoke test
│
├── docs/                        # Additional documentation
│   ├── MIGRATION_GUIDE.md         # Migration from DS-AIOS to DS-EO
│   ├── COMPATIBILITY.md           # OpenClaw version compatibility
│   └── CONTRIBUTING.md            # Contribution guidelines
│
├── examples/                    # Usage examples
│   └── minimal-workflow.md        # "From request to delivery" walkthrough
│
├── dispatcher/                  # Dispatcher/Workflow Engine layer (v0.4)
│   ├── ARCHITECTURE.md           # Architecture overview
│   ├── IMPLEMENTATION_PLAN.md    # Build plan with priorities and risks
│   ├── PROTOCOL.md               # Runtime contract between components
│   ├── STATE_SCHEMA.md           # Persistent state file formats
│   ├── SKILL.md                  # PM-facing dispatcher skill instructions
│   ├── PM_DISPATCHER_SKILL.md    # Operational guide for PM agent
│   ├── registry.py              # Agent registry loader with checksum validation
│   ├── engine.py                 # G0-G4 gate machine (data-driven from YAML)
│   ├── state_manager.py          # Per-task persistent state + audit logs
│   ├── dispatch.py               # Unified dispatcher API for PM orchestration
│   ├── session_dispatch/         # sessions_spawn wrapper for agent handoffs
│   │   └── engine.py
│   ├── binding_defs/             # Gateway entry-point bindings (YAML)
│   │   └── entry_points.yaml
│   ├── workflow_defs/            # Data-driven workflow definitions
│   │   └── default.yaml          # G0-G4 gate machine definition
│   └── __init__.py              # Package initialization
│
├── ds_eo_openclaw/              # Python package modules
    ├── __init__.py              # Package initialization
    ├── intake/                  # Task Intake Manager (v0.5)
    │   ├── __init__.py          # Public API exports (TaskIntakeManager, create_task_intake)
    │   └── task_intake.py       # PM-driven task intake with dedup, workspace creation, CTO handoff prep
    ├── session_health/          # Session Health monitoring (v0.6)
    │   ├── __init__.py          # Public API exports
    │   ├── enums.py             # SessionHealthState, LifecycleAction, MonitorStatus
    │   ├── config.py            # YAML-based configuration with conservative defaults
    │   ├── discoverer.py        # Session discovery extending LivenessChecker
    │   ├── classifier.py        # Deterministic multi-signal → single classification
    │   ├── policy.py            # Health→action policy map with 3 safety layers
    │   ├── executor.py          # Action execution with verify-then-persist pattern
    │   ├── monitor.py           # Scheduling loop: discover→classify→policy→execute→audit
    │   └── audit.py             # Persistent per-cycle audit trail
    └── workflow/
        ├── __init__.py
        ├── state_engine.py      # 11-state state machine with auto-advance
        ├── audit_log.py         # Immutable audit trail with hash chain
        ├── config.py            # Mode config with per-task overrides
        ├── selector.py          # Atomic mode switching
        ├── notifications.py     # Auto-mode notification messages
        ├── timeout_config.py    # Per-state timeouts
        ├── stall_detection.py   # PM monitoring integration
        ├── escalation.py        # Blocker escalation chain
        └── failure_detector.py  # Repeated failure detection
```

## Roles

| Role | Emoji | Description | Default Model |
|------|-------|-------------|---------------|
| CTO / Architect | 🏗️ | Architecture, planning, final approval authority | `ollama/qwen3.6:35b` |
| Code Implementer | 💻 | Execute approved plans, produce working code | `ollama/ornith:35b` |
| Senior Code Reviewer | 🔍 | Independent verification and quality assessment | `ollama/laguna-xs-2.1:q4_K_M` |
| Project Manager | 📋 | Process oversight — task lifecycle, status tracking, release management | `ollama/gpt-oss:20b` |

## Development Workflow

### Canonical Flow (PM-driven programmatic orchestration)

```
/eo task → PM dispatches CTO (S0→S1)
    │
    ├── G1: User approves CTO_PLAN.md
    │   └── Dispatcher delegates to Implementer (S2) via sessions_spawn()
    │       ├── Implementation complete → dispatcher routes to Reviewer (S3)
    │       ├── Review approved → dispatcher routes to CTO for G4 (S4)
    │       └── User approves → PM completes S5 (PM_CLOSED + cleanup)
    │
    └── Rejection loops: any gate can route work back to Implementer (S2)
        Dispatcher handles phase backtracking automatically
```

### How It Works

1. **Entry point**: Gateway binding routes `/eo task` → PM agent
2. **Task creation**: `Dispatcher.open_task()` creates S0_OPEN state + snapshots agent registry checksum
3. **Planning**: CTO writes CTO_PLAN.md; user approves via G1
4. **Implementation**: Dispatcher spawns Implementer with isolated context via `sessions_spawn(agent="implementer", context="isolated")`
5. **Review**: Reviewer independently verifies; REVIEW_REPORT.md produced
6. **Final approval**: CTO issues G4 decision; user confirms; PM runs S5 cleanup
7. **Completion**: PM_CLOSED.md written, project status updated, Git push (with user confirmation)

### Routing Design Principle

**Gateway bindings expose only entry points — all workflow routing lives inside DS-EO.**

The dispatcher engine reads `workflow_defs/default.yaml` to determine phase transitions, authority requirements, and artifact prerequisites. No routing logic is embedded in OpenClaw gateway configuration. This keeps the routing contract portable across platforms.

Four formal approval gates ensure quality at every phase transition. See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Roadmap

- **v0.1** (completed): Extract, package, and install DS-EO OpenClaw Edition
- **v0.2** (completed): Protocol & governance consistency migration
- **v0.3** (completed): Automatic Mode — full workflow engine, audit trail, mode selector, failure handling, and slash command skill
- **v0.4** (completed): Dispatcher/Workflow Engine layer
  - `dispatcher/registry.py` — Agent registry loader with SHA256 integrity checksums
  - `dispatcher/engine.py` — G0-G4 gate machine state machine (data-driven from YAML)
  - `dispatcher/state_manager.py` — Persistent per-task state with atomic writes + audit logs
  - `dispatcher/dispatch.py` — Unified dispatcher API for PM-driven task orchestration
  - `dispatcher/session_dispatch/` — `sessions_spawn()` wrapper for agent-to-agent handoffs
  - `dispatcher/binding_defs/` — Gateway entry-point bindings (PM only, no workflow logic)
  - `dispatcher/PM_DISPATCHER_SKILL.md` — Operational guide for PM agent use of dispatcher
  - PM tool policy updated: exec + write + sessions_list + memory access
  - CTO tool policy updated: sessions_spawn + sessions_send for delegation
  - All internal routing lives in dispatcher, not gateway config (design constraint met)
- **v0.5** (completed): Task Intake Manager Layer
  - `ds_eo_openclaw/intake/` — PM-driven task intake with dedup, workspace creation, and CTO handoff preparation
  - `tests/test_task_intake.py` — 17 tests covering all spec acceptance criteria
- **v0.6** (completed): Session Health and Lifecycle Management Layer
  - `ds_eo_openclaw/session_health/` — Session discovery, classification, policy, and lifecycle management
    - `enums.py` — SessionHealthState (11 states), LifecycleAction (11 actions), MonitorStatus (3 statuses)
    - `config.py` — YAML-based configuration with conservative defaults
    - `discoverer.py` — Session discovery extending LivenessChecker (8 health indicators)
    - `classifier.py` — Deterministic multi-signal → single classification
    - `policy.py` — Health→action policy map with 3 safety layers
    - `executor.py` — Action execution with verify-then-persist pattern
    - `monitor.py` — Scheduling loop: discover→classify→policy→execute→audit pipeline
    - `audit.py` — Persistent per-cycle audit trail
  - Configurable thresholds, OBSERVING mode by default
  - Total tests across all modules: 315 (0 failures)
- **v0.7** (in-progress): Runtime Investigation and Upstream Bug Reports
  - TASK_20260808_032: Token accounting and run abort state sync bug analysis
  - TASK_20260808_033: Cross-role compaction timeout root cause investigation
  - TASK_DS_EO_031: Upstream bug report for `resolveSessionModelRef` precedence fix
- **v1.0** (planned): Platform abstraction layer for multi-platform editions
- **Future**: Additional platform editions (Claude, Codex, Gemini)


# License

MIT

Copyright (c) 2026 Deepsim Intelligence Technology Inc.


---

## Project Maintainer

**Dr. Shouke Wei (魏守科)**  
Founder, Deepsim Intelligence Technology Inc.

DS-EO is developed and maintained by the Deepsim AI Lab at Deepsim Intelligence Technology Inc.
---

*Built with DS-EO OpenClaw Edition.*
