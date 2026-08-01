# DS-EO OpenClaw Edition

**DeepSim Engineering Organization — OpenClaw Edition**

A reusable engineering organization framework that transforms an AI agent platform into a disciplined software engineering team. This is the first platform-specific edition (OpenClaw).

---

## What Is DS-EO?

DS-EO provides:

- **Engineering roles** with clear responsibilities and tool policies
- **Communication protocols** for agent-to-agent messaging
- **Development workflows** with formal approval gates
- **Review processes** with scoring rubrics
- **Task lifecycle management** from planning through delivery
- **Portable configuration** that installs into any OpenClaw host

## Architecture: Two-Layer Model

DS-EO separates the **engineering organization** (who builds) from the **runtime product** (what is built):

```
User Request
    │
    ▼
Engineering Organization (CTO → Implementer → Reviewer → CTO)
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
5. Verify the installation

See [INSTALLATION.md](INSTALLATION.md) for detailed steps.

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
│   ├── backup_openclaw_config.sh    # Pre-install backup
│   ├── generate_openclaw_config.sh  # Agent config generator
│   ├── deploy_protocols.sh          # Protocol deployment
│   ├── deploy_agents.sh             # Prompt file deployment
│   └── verify_installation.sh       # Post-install verification
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
└── examples/                    # Usage examples
    └── minimal-workflow.md        # "From request to delivery" walkthrough
```

## Roles

| Role | Emoji | Description | Default Model |
|------|-------|-------------|---------------|
| CTO / Architect | 🏗️ | Architecture, planning, final approval authority | `ollama/qwen3.6:35b` |
| Code Implementer | 💻 | Execute approved plans, produce working code | `ollama/ornith:35b` |
| Senior Code Reviewer | 🔍 | Independent verification and quality assessment | `ollama/laguna-xs-2.1:q4_K_M` |
| Project Manager | 📋 | Process oversight — task lifecycle, status tracking, release management | `ollama/qwen3.6:35b` |

## Development Workflow

```
User Request → PM Lifecycle Coordination → CTO Plan (G1) → Implementer (G2) → Reviewer (G3) → CTO Approve (G4)
```

Four formal approval gates ensure quality at every phase transition. See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Roadmap

- **v0.1** (completed): Extract, package, and install DS-EO OpenClaw Edition
- **v0.2** (completed): Protocol & governance consistency migration
- **v1.0**: Platform abstraction layer for multi-platform editions
- **Future**: Additional platform editions (Claude, Codex, Gemini)
- **v1.0**: Platform abstraction layer for multi-platform editions
- **Future**: Additional platform editions (Claude, Codex, Gemini)

## License

MIT

Copyright (c) 2026 Deepsim Intelligence Technology Inc.


---

## Project Maintainer

**Dr. Shouke Wei (魏守科)**  
Founder, Deepsim Intelligence Technology Inc.

DS-EO is developed and maintained by the Deepsim AI Lab at Deepsim Intelligence Technology Inc.
---

*Built with DS-EO OpenClaw Edition.*
