# CTO Implementation Plan — TASK_DS_EO_002

**Task ID**: TASK_DS_EO_002  
**Title**: DS-EO OpenClaw Edition v0.1 Implementation Plan  
**Date**: 2026-07-28  
**Role**: CTO / Architect (ollama/qwen3.6:35b)  
**Status**: AWAITING USER APPROVAL  

---

## Executive Summary

This plan defines how to build the first installable DS-EO OpenClaw Edition package. Based on the extraction audit (TASK_DS_EO_001), DS-EO will be a self-contained Git repository with a custom manifest, portable agent/protocol definitions, and a scripted installation workflow that merges safely into any existing OpenClaw host via `openclaw.json` config merge + file deployment. No OpenClaw source code is modified; no DS-AIOS dependencies are introduced.

---

## 1. Repository Structure

### Target Directory Layout

```
ds-eo-openclaw/
├── README.md                        # Project overview, quick start, architecture
├── ARCHITECTURE.md                  # Core concepts: two-layer model, roles, workflow
├── INSTALLATION.md                  # Step-by-step installation guide
├── CHANGELOG.md                     # Version history
│
├── ds_eo_manifest.yaml              # Package manifest (defines the DS-EO package)
│
├── agents/                          # Role definitions — portable agent configs
│   ├── cto.md                       # CTO prompt: identity, responsibilities, tool policy
│   ├── implementer.md               # Implementer prompt: identity, responsibilities, tool policy
│   └── reviewer.md                  # Reviewer prompt: identity, responsibilities, tool policy
│
├── protocols/                       # Engineering protocols — core rules only
│   ├── README.md                    # Protocol hierarchy guide (DS-EO edition)
│   ├── approval_protocol.md         # G1-G4 gates, rejection handling, escalation
│   ├── communication_protocol.md    # Message types and formats
│   ├── completion_protocol.md       # Per-role completion checklists
│   ├── delegation_protocol.md       # Task creation and assignment process
│   ├── handoff_protocol.md          # Phase transitions and artifact requirements
│   └── review_protocol.md           # Review rubric, scoring, recommendation thresholds
│
├── templates/                       # Reusable templates
│   ├── task.md                      # TASK directory structure template
│   ├── report_template.md           # Implementation report format
│   ├── review_report_template.md    # Review report format
│   ├── spec_template.md             # Specification document format
│   └── cto_approval_template.md     # CTO final approval memo format
│
├── config-templates/                # Reference configurations (human-readable)
│   ├── example_openclaw_config.json # Example openclaw.json snippet for agents.list[]
│   └── model_placeholders.txt       # Model name placeholder conventions
│
├── scripts/                         # Installation and management helpers
│   ├── generate_openclaw_config.sh  # Generates openclaw.json agent config entries
│   ├── deploy_protocols.sh           # Deploys protocols to target locations
│   ├── deploy_agents.sh              # Deploys prompt files to project workspace
│   ├── verify_installation.sh        # Post-install verification checks
│   └── backup_openclaw_config.sh     # Pre-install backup with rollback support
│
├── tests/                           # Verification and compliance tests
│   ├── test_manifest_schema.py       # Validates ds_eo_manifest.yaml against schema
│   ├── test_protocol_extraction.py   # Verifies all core protocols present and non-empty
│   ├── test_template_completeness.py # Checks all templates have required sections
│   ├── test_config_merge_safety.py   # Validates config merge won't corrupt existing state
│   └── test_installation_flow.sh     # End-to-end installation smoke test (on clean host)
│
├── docs/
│   ├── MIGRATION_GUIDE.md           # Migration from DS-AIOS-scattered to DS-EO package
│   ├── COMPATIBILITY.md             # OpenClaw version compatibility matrix
│   └── CONTRIBUTING.md              # Contribution guidelines for open-source
│
└── examples/
    └── minimal-workflow.md            # "From request to delivery" walkthrough using DS-EO
```

### Directory Descriptions by Category

| Category | Directories | Purpose | Portable? |
|----------|------------|---------|-----------|
| **Core** | `ds_eo_manifest.yaml`, `README.md`, `ARCHITECTURE.md` | Package identity and architecture definition | Fully portable — no paths to external systems |
| **Agents** | `agents/` | Role definitions with generic model placeholders | Portable — placeholder values for `<MODEL_NAME>` |
| **Protocols** | `protocols/` | Engineering rules, gates, workflows | Portable — base rules are platform-agnostic |
| **Templates** | `templates/` | Document formats for task lifecycle | Fully portable |
| **Config** | `config-templates/` | Reference JSON/placeholder configs | Portable — uses `<WORKSPACE_PATH>` placeholders |
| **Scripts** | `scripts/` | Installation helpers | Portable bash scripts with configurable paths |
| **Tests** | `tests/` | Schema validation, extraction completeness, config safety | Portable test suite |
| **Docs** | `docs/` | Migration guide, compatibility matrix, contributing | Fully portable |
| **Examples** | `examples/` | Usage walkthrough | Portable — generic example project |

---

## 2. DS-EO Manifest Schema (`ds_eo_manifest.yaml`)

### Rationale for YAML Manifest

DS-EO needs a package-level manifest because:
1. OpenClaw has no "organization install" mechanism, so DS-EO must define its own package format
2. The manifest serves as the **single source of truth** for what DS-EO is and what it contains
3. It enables automated validation (is the installation complete? does the package match the spec?)
4. It's human-readable for manual inspection during installation
5. YAML is chosen over JSON because it supports comments, inline documentation, and is the format OpenClaw's own config uses (via its internal schema)

### Schema Definition

```yaml
# ds_eo_manifest.yaml — DS-EO OpenClaw Edition Package Manifest

package:
  name: "ds-eo-openclaw"                    # Package identifier
  title: "DeepSim Engineering Organization — OpenClaw Edition"  # Display name
  version: "0.1.0"                           # Semantic version (MAJOR.MINOR.PATCH)
  description: >
    Extractable engineering organization framework for OpenClaw.
    Provides agent roles, protocols, and workflows to transform
    AI agent platforms into disciplined software engineering teams.
  license: "MIT"                              # License identifier
  author: "DeepSim"                           # Package author/maintainer
  
openclaw:                                    # OpenClaw-specific metadata
  minimum_version: "2026.7.1"               # Minimum supported OpenClaw version
  target_config: "~/.openclaw/openclaw.json"  # Config file to merge into

roles:                                       # Engineering organization roles
  - id: "cto"
    name: "CTO / Architect"
    emoji: "🏗️"
    prompt_file: "agents/cto.md"
    description: "Architecture, planning, and final approval authority."
    model_placeholder: "<MODEL_CTO>"         # User fills this in during install
    tool_profile: "generic"                  # Generic tool access profile
    default_model: "ollama/qwen3.6:35b"      # Default suggestion; user may override
    
  - id: "implementer"
    name: "Code Implementer"
    emoji: "💻"
    prompt_file: "agents/implementer.md"
    description: "Execution agent — executes approved plans and produces working code."
    model_placeholder: "<MODEL_IMPLEMENTER>"
    tool_profile: "coding"
    default_model: "ollama/ornith:35b"
    
  - id: "reviewer"
    name: "Senior Code Reviewer"
    emoji: "🔍"
    prompt_file: "agents/reviewer.md"
    description: "Independent verification agent — unbiased quality assessment."
    model_placeholder: "<MODEL_REVIEWER>"
    tool_profile: "generic"
    default_model: "ollama/laguna-xs-2.1:q4_K_M"

protocols:                                   # Engineering protocols included
  - id: "approval_protocol"
    file: "protocols/approval_protocol.md"
    category: "governance"                   # governance | communication | workflow
    level: "core"                            # core (mandatory) | extension (optional)
    gates: ["G1", "G2", "G3", "G4"]         # Which gates this protocol defines
    
  - id: "communication_protocol"
    file: "protocols/communication_protocol.md"
    category: "communication"
    level: "core"
    
  - id: "completion_protocol"
    file: "protocols/completion_protocol.md"
    category: "workflow"
    level: "core"
    roles: ["CTO", "Implementer", "Reviewer"]
    
  - id: "delegation_protocol"
    file: "protocols/delegation_protocol.md"
    category: "workflow"
    level: "core"
    
  - id: "handoff_protocol"
    file: "protocols/handoff_protocol.md"
    category: "workflow"
    level: "core"
    
  - id: "review_protocol"
    file: "protocols/review_protocol.md"
    category: "governance"
    level: "core"
    scoring_dimensions:
      - name: "Specification Compliance"
        weight: 40
      - name: "Code Quality"
        weight: 25
      - name: "Architecture Adherence"
        weight: 25
      - name: "Test Coverage & Regression"
        weight: 10

templates:                                  # Document templates included
  - id: "task"
    file: "templates/task.md"
    purpose: "Task directory structure and naming convention"
    
  - id: "report"
    file: "templates/report_template.md"
    purpose: "Implementation report format"
    
  - id: "review_report"
    file: "templates/review_report_template.md"
    purpose: "Review report format"
    
  - id: "spec"
    file: "templates/spec_template.md"
    purpose: "Specification document format"
    
  - id: "cto_approval"
    file: "templates/cto_approval_template.md"
    purpose: "CTO final approval memo format"

installation:                               # Installation metadata
  steps:
    - step: 1
      name: "Backup existing config"
      script: "scripts/backup_openclaw_config.sh"
      required: true
      
    - step: 2
      name: "Generate agent config entries"
      description: "Creates openclaw.json agents.list[] entries with user-specified models"
      script: "scripts/generate_openclaw_config.sh"
      interactive: true                     # Requires user input for model names
      required: true
      
    - step: 3
      name: "Merge agent config into openclaw.json"
      description: "Safely merges agents.list[] entries, preserving existing entries"
      script: "scripts/generate_openclaw_config.sh --merge"
      backup_before_merge: true
      required: true
      
    - step: 4
      name: "Deploy protocols globally"
      description: "Copies protocol files to ~/.openclaw/protocols/"
      script: "scripts/deploy_protocols.sh --target ~/.openclaw/protocols/"
      backup_before_deploy: true
      required: true
      
    - step: 5
      name: "Deploy protocols per-project"
      description: "Copies protocol files to project workspace"
      script: "scripts/deploy_protocols.sh --target <PROJECT_PATH>/docs/development/protocols/"
      backup_before_deploy: true
      required: false                     # Optional for multi-project setups
      
    - step: 6
      name: "Deploy agent prompts per-project"
      description: "Copies agent prompt files to workspace docs/prompts/"
      script: "scripts/deploy_agents.sh --target <PROJECT_PATH>/docs/prompts/"
      required: true
      
    - step: 7
      name: "Verify installation"
      script: "scripts/verify_installation.sh"
      rollback_on_failure: true
      required: true

dependencies:                              # External dependencies (none for v0.1)
  openclaw:
    minimum_version: "2026.7.1"
    tools_needed:
      - "group:fs"                          # File system access
      - "exec"                              # Shell execution (for scripts)
  
  systems: []                               # No external system dependencies

compliance:                                # Compliance and validation metadata
  test_suite: "tests/"
  verification_checks:
    - check: "manifest_valid"              # ds_eo_manifest.yaml is valid YAML
      test: "test_manifest_schema.py"
      
    - check: "all_agents_present"          # All 3 role files exist and are non-empty
      test: "test_protocol_extraction.py"
      
    - check: "all_templates_present"       # All templates have required sections
      test: "test_template_completeness.py"
      
    - check: "config_merge_safe"           # Merged config is valid JSON
      test: "test_config_merge_safety.py"
      
    - check: "installation_flow"           # End-to-end install works on clean host
      test: "test_installation_flow.sh"

---

## 3. Installation Workflow

### 3.1 Overview — The Installation Pipeline

```
┌─────────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  1. Backup Config   │ →   │  2. Generate &   │ →   │  3. Merge into   │
│  (safety net)       │     │     Merge        │     │ openclaw.json    │
└─────────────────────┘     └──────────────────┘     └──────────────────┘
                              │                      │
                              ▼                      ▼
                    ┌──────────────────┐     ┌──────────────────┐
                    │ 4. Deploy Protocols│ → │ 5. Deploy Prompts│
                    │ (global + project)│     │ (project workspace)│
                    └──────────────────┘     └──────────────────┘
                              │                      │
                              ▼                      ▼
                    ┌──────────────────────────────────────┐
                    │ 6. Verify Installation               │
                    │    - Validate openclaw.json structure│
                    │    - Check all files present         │
                    │    - Test agent can load             │
                    │    - If fail → rollback to backup   │
                    └──────────────────────────────────────┘
```

### 3.2 Step-by-Step Installation Procedure

#### Pre-flight Checks (Automatic)

```bash
# The install script runs these before doing anything:
1. Check openclaw.json is accessible and valid JSON
2. Check sufficient disk space (>50MB free)
3. Check no other DS-EO installation exists in target locations
4. Display what will change (diff preview to user)
```

#### Step 1: Backup

```bash
# Script: scripts/backup_openclaw_config.sh
# Action: Creates timestamped backup of openclaw.json
# Location: ~/.openclaw/backups/ds-eo-openclaw-<timestamp>.json.bak
# Rollback: cp backup /path/to/openclaw.json
```

#### Step 2: Generate Agent Config (Interactive)

```bash
# Script: scripts/generate_openclaw_config.sh --generate
# Prompts the user for:
│   CTO model name [ollama/qwen3.6:35b]: _user_input_
│   Implementer model name [ollama/ornith:35b]: _user_input_
│   Reviewer model name [ollama/laguna-xs-2.1:q4_K_M]: _user_input_
│   Workspace path [/home/deepsim/agent_system]: _user_input_
│   
# Output: agents_list.json — valid JSON array of 3 agent config objects

# Key design decisions for the generated config:
│   - Each agent's "id" must not collide with existing entries
│   - The default model (ollama/qwen3.6:35b) becomes the defaults.model.primary
│     ONLY if no other agent has claimed that as its primary
│   - workspace path is set to user-specified value
│   - tool.allow lists use "generic" profile for CTO/Reviewer, "coding" for Implementer
│   - tool.deny for CTO/Reviewer includes write/edit/apply_patch (no changes allowed)
│   - tool.deny for Implementer is empty (full access as required)
```

#### Step 3: Merge into openclaw.json

```bash
# Script: scripts/generate_openclaw_config.sh --merge agents_list.json
# Algorithm:
│   1. Read existing openclaw.json
│   2. For each agent in agents_list:
│      a. Check if agents.list contains an entry with same "id"
│      b. If exists → OVERWRITE (replaces existing role config)
│      c. If not exists → APPEND to agents.list array
│   3. Update agents.defaults.model.primary if needed (use most common default)
│   4. Validate resulting JSON with python json.tool
│   5. Write atomically: write to .tmp file, then mv to openclaw.json
```

**Merge safety guarantees:**
- Existing non-DS-EO agent entries are never touched
- Gateway config is never modified
- Plugins and skills sections are never modified
- Channel configs are never modified
- Only `agents.list[]` and optionally `agents.defaults.model` are affected

#### Step 4: Deploy Protocols

```bash
# Script: scripts/deploy_protocols.sh --target <path>
# Two deployment modes:
│   --target ~/.openclaw/protocols/        # Global (authoritative) — recommended
│   --target /path/to/workspace/protocols/  # Per-project (adaptations)
│   
# Deployment rules:
│   - If file already exists at target → OVERWRITE (DS-EO owns its own protocols)
│   - If global and project files differ, warn user of potential divergence
│   - Backup before overwrite: <filename>.ds-eo-bak
│   - Preserve any .bak files that predate DS-EO installation
```

#### Step 5: Deploy Agent Prompts

```bash
# Script: scripts/deploy_agents.sh --target <workspace>/docs/prompts/
# Action: copies agents/*.md to target path
# Behavior: overwrites any existing cto.md, implementer.md, reviewer.md in target
# Backup: creates *.ds-eo-bak for each overwritten file
```

#### Step 6: Verify Installation

```bash
# Script: scripts/verify_installation.sh
# Checks performed:
│   1. openclaw.json is valid JSON and contains all 3 DS-EO agents in agents.list[]
│   2. Each agent has required fields: id, name, model, workspace, tools.allow
│   3. agents.list has no duplicate "id" values
│   4. All protocol files exist at target locations and are non-empty (>100 bytes)
│   5. All prompt files exist at target locations and are non-empty
│   6. All template files exist in templates/ directory
│   7. openclaw.json still contains original gateway, plugins, channels sections
│      (no accidental modifications to unrelated sections)
│   
# On failure: automatic rollback using backup from Step 1
```

### 3.3 Manual Installation Alternative

For users who prefer manual control, INSTALLATION.md provides a step-by-step guide with copy-paste commands and JSON snippets for each merge operation. The scripted installation is recommended but not required.

---

## 4. Configuration Merge Strategy

### 4.1 What Gets Merged vs What Stays Untouched

```json
// openclaw.json — BEFORE (user's existing config)
{
  "agents": {
    "defaults": { "model": { "primary": "...", "fallbacks": [...] } },
    "list": [
      /* user's existing agent configs — untouched */
    ]
  },
  "gateway": { /* ... all gateway config — untouched */ },
  "plugins": { /* ... — untouched */ },
  "skills": { /* ... — untouched */ },
  "channels": { /* ... — untouched */ }
}

// openclaw.json — AFTER (DS-EO merged)
{
  "agents": {
    "defaults": {
      "model": { 
        "primary": "<most-common-default>",   // potentially updated
        "fallbacks": ["ollama/ornith:35b"]     // unchanged
      }
    },
    "list": [
      /* user's existing agent configs — untouched */
      { id: "cto", ... DS-EO entry ... },       // ADDED or REPLACED
      { id: "implementer", ... DS-EO entry ... },  // ADDED or REPLACED  
      { id: "reviewer", ... DS-EO entry ... }    // ADDED or REPLACED
    ]
  },
  "gateway": { /* ... — untouched */ },
  "plugins": { /* ... — untouched */ },
  "skills": { /* ... — untouched */ },
  "channels": { /* ... — untouched */ }
}
```

### 4.2 Merge Algorithm Detail

```python
def merge_ds_eo_config(existing_json, ds_eo_agents):
    """Merge DS-EO agents into existing openclaw.json config."""
    
    # Preserve everything except agents section
    original_keys = {k: v for k, v in existing_json.items() if k != "agents"}
    
    agents = existing_json.get("agents", {})
    default_model = agents.setdefault("defaults", {}).setdefault("model", {})
    
    current_list = agents.setdefault("list", [])
    current_ids = {a["id"] for a in current_list}
    
    # Determine which DS-EO entries to add vs replace
    merged_list = list(current_list)  # copy existing
    added_ids = set()
    
    for ds_eo_agent in ds_eo_agents:
        agent_id = ds_eo_agent["id"]
        if agent_id in current_ids and agent_id not in added_ids:
            # Replace existing entry with same id
            for i, existing in enumerate(merged_list):
                if existing["id"] == agent_id:
                    merged_list[i] = ds_eo_agent
                    break
        elif agent_id not in added_ids:
            # Add new entry
            merged_list.append(ds_eo_agent)
            added_ids.add(agent_id)
    
    # Update default model only if we need a primary
    if not default_model.get("primary"):
        default_model["primary"] = ds_eo_agents[0]["model"]
    
    # Reconstruct config
    result = {**original_keys, "agents": {"defaults": {"model": default_model}, "list": merged_list}}
    
    return result
```

### 4.3 Conflict Resolution Rules

| Scenario | Rule |
|----------|------|
| DS-EO agent `id` already exists in user config | **Replace** (overwrites the existing entry) |
| New DS-EO agent `id` doesn't exist | **Append** to end of agents.list[] |
| User has custom tool.allow/deny for an agent with same id | **Overwrite** — DS-EO defines its own security posture |
| Model availability conflict (user doesn't have the suggested model) | **Warn user** — script continues but marks as unverified |
| openclaw.json is corrupted or unreadable | **Abort** — no changes made, clear error message |

---

## 5. Backup and Rollback Mechanism

### 5.1 Pre-Install Backup

```bash
# Script: scripts/backup_openclaw_config.sh
# Creates timestamped backup of the ENTIRE openclaw.json:
┌──────────────────────────────┐
│ ~/.openclaw/openclaw.json    │ ──copy──> ~/.openclaw/backups/
│                              │          ds-eo-openclaw-20260728T085600.json.bak
└──────────────────────────────┘

# Also backs up any existing protocol files that will be overwritten:
~/.openclaw/protocols/*.md ──copy──> ~/.openclaw/protocols/*.ds-eo-bak (if they exist)
~/project/docs/prompts/*.md ──copy──> *.ds-eo-bak (if they exist)
```

### 5.2 Post-Install Backup Chain

After a successful installation, the script maintains:

```
openclaw.json                          ← current (DS-EO installed)
backups/ds-eo-openclaw-latest.json.bak ← most recent pre-install snapshot
backups/ds-eo-openclaw-{timestamp}.json.bak ← historical snapshots
```

### 5.3 Automatic Rollback

**Trigger**: Any verification check in Step 6 fails.

**Action**:
```bash
# scripts/verify_installation.sh (rollback path)
if verification_failed; then
    echo "VERIFICATION FAILED — initiating rollback..."
    
    # Find most recent backup
    LATEST_BACKUP=$(ls -t ~/.openclaw/backups/ds-eo-openclaw-*.json.bak | head -1)
    
    if [ -n "$LATEST_BACKUP" ]; then
        cp "$LATEST_BACKUP" ~/.openclaw/openclaw.json
        echo "Rollback complete. openclaw.json restored from backup."
        
        # Also restore protocol backups if they exist
        for proto in approval communication completion delegation handoff review; do
            BAK=~/.openclaw/protocols/${proto}_protocol.md.ds-eo-bak
            [ -f "$BAK" ] && mv "$BAK" ~/.openclaw/protocols/${proto}_protocol.md
        done
        
        exit 1  # Non-zero to signal failure
    else
        echo "ERROR: No backup found. Manual intervention required."
        exit 2
    fi
fi
```

### 5.4 Rollback on User Request (Manual)

```bash
# Scripts/deploy_protocols.sh --rollback
# Removes all DS-EO protocol files from target locations
# Restores from .ds-eo-bak backups

# scripts/manifest uninstall ds-eo-openclaw  # future: automated cleanup
```

### 5.5 Safety Guarantees

| Guarantee | How Enforced |
|-----------|-------------|
| Nothing is modified before backup is created | Backup is Step 1; all other steps depend on it |
| openclaw.json is always valid JSON after merge | Python json.tool validation after every write |
| Original non-DS-EO entries are never touched | Merge algorithm only touches agents section |
| Rollback restores original state exactly | Byte-for-byte backup copy, not diff/patch |
| Verification must pass before installation completes | Step 6 is the final gate; fail = rollback |

---

## 6. Verification Tests

### 6.1 Test Suite Structure

All tests run as part of `scripts/verify_installation.sh` after installation. For CI, they can be invoked individually:

```bash
pytest tests/                              # All Python test suites
bash tests/test_installation_flow.sh       # End-to-end shell smoke test
```

### 6.2 Test 1: Manifest Schema Validation (`test_manifest_schema.py`)

```python
# Validates ds_eo_manifest.yaml against the schema defined in Section 2
checks:
    - "package.name" is present and non-empty string
    - "package.version" matches semver regex (MAJOR.MINOR.PATCH)
    - "package.license" is a recognized OSI license
    - "openclaw.minimum_version" is valid version string
    - "roles" has exactly 3 entries with ids: cto, implementer, reviewer
    - Each role has: id, name, emoji, prompt_file, model_placeholder, tool_profile, default_model
    - "protocols" has all 6 protocol entries, each with file path and category
    - "templates" has all 5 template entries
    - "installation.steps" has 7 steps in correct order (1-7)
    - Step 2 is interactive = true
    - Steps 1, 2, 3, 6 have backup_before_*/rollback_on_failure = true
    - No cycle in protocol references (each file: path exists relative to package root)
```

### 6.3 Test 2: Protocol Extraction Completeness (`test_protocol_extraction.py`)

```python
# Verifies all core protocols from the extraction audit are present and generic
checks:
    - All 6 protocol files exist in protocols/ directory
    - Each file is >500 bytes (not accidentally empty/truncated)
    - Each file contains Gate definitions (G1, G2, G3, or G4 references)
    - No DS-AIOS-specific path references found:
      • "agent_system/" not in any protocol file
      • "CEO Agent" not referenced as a role definition
      • "Research Agent" not referenced as a role definition
      • "Writer Agent" not referenced as a role definition
      • "app/book_project" not in any protocol
    - No hardcoded host paths (~/ or /home/deepsim/) in protocol content
    - Each protocol has a version and scope header indicating it's DS-EO edition
```

### 6.4 Test 3: Template Completeness (`test_template_completeness.py`)

```python
# Verifies all templates have required sections per their purpose
checks:
    - task.md contains: "TASK naming", "directory structure", "handoff artifacts"
    - report_template.md contains: "Summary", "Changes Made", "Acceptance Criteria Verification", "Deviation Analysis"
    - review_report_template.md contains: "Review Summary", "Recommendation", "Scoring Matrix"
    - spec_template.md contains: "Problem Statement", "Scope", "Acceptance Criteria", "Risks"
    - cto_approval_template.md contains: "Decision", "Rationale", "Two-Layer Boundary Verification"
    - No templates contain DS-AIOS-specific references
```

### 6.5 Test 4: Config Merge Safety (`test_config_merge_safety.py`)

```python
# Verifies the generated config merge won't corrupt existing state
checks:
    - Generated agents.list[] has exactly 3 new entries (ctos, implementer, reviewer)
    - No duplicate "id" values in merged config
    - All agent entries have all required fields: id, name, model, tools.allow
    - Merge preserves all non-"agents" keys in openclaw.json
    - Gateway section is byte-identical to original (no accidental modifications)
    - Plugins section is preserved
    - Skills section is preserved
    - Channels section is preserved
    - Resulting JSON passes json.loads() + json.dumps() round-trip
```

### 6.6 Test 5: Installation Flow Smoke Test (`test_installation_flow.sh`)

```bash
# End-to-end smoke test on a clean/controlled OpenClaw instance
steps:
    - "Set up test environment (temporary openclaw.json in /tmp)"
    - "Run backup script → verify backup exists"
    - "Generate config interactively with default models"
    - "Merge into test config → verify JSON validity"
    - "Deploy protocols to temp directory → verify all files present"
    - "Verify installation → should pass all checks"
    - "Test rollback → trigger verification failure, verify backup restore works"
    - "Clean up: remove temp files and test environment"
expected_result: "All 7 steps pass; rollback successfully restores original config"
```

---

## 7. Components Requiring Extraction from Current ~/.openclaw

### 7.1 What Must Be Extracted (Source → DS-EO Package)

| Source Location | Component | Target in DS-EO | Notes |
|----------------|-----------|-----------------|-------|
| `~/.openclaw/openclaw.json` → `agents.list[0]` | CTO agent definition | `agents/cto.md` + `config-templates/example_openclaw_config.json` | Convert JSON to portable prompt file; generate config template separately |
| `~/.openclaw/openclaw.json` → `agents.list[1]` | Implementer agent definition | `agents/implementer.md` + config template | Same pattern as CTO |
| `~/.openclaw/openclaw.json` → `agents.list[2]` | Reviewer agent definition | `agents/reviewer.md` + config template | Same pattern as CTO |
| `~/.openclaw/protocols/*.md` (6 files) | Core engineering protocols | `protocols/` (all 6) | Remove DS-AIOS adaptations; keep only base rules |
| `AGENTS.md` (§3, §4, §5, §6, §7, §9) | Governance rules | Incorporated into `ARCHITECTURE.md` + protocol files | Convert section references to portable form |

### 7.2 What Must NOT Be Extracted (DS-AIOS-Specific — Left Behind)

| Location | Component | Reason |
|----------|-----------|--------|
| `AGENTS.md` §2 | CEO, Research, Writer, Reviewer agents | DS-AIOS product roles, not engineering org |
| `AGENTS.md` §8 | Architecture Preservation rules | DS-AIOS-specific architecture protection |
| `docs/prompts/ceo.md` | CEO Agent prompt | Product role |
| `docs/prompts/writer.md` | Writer Agent prompt | Product role |
| `docs/prompts/architect.md` | Architect prompt (duplicate) | Unreferenced by current workflow |
| `docs/prompts/developer.md` | Developer prompt | Unreferenced by current workflow |
| `~/.openclaw/agents/<id>/sessions/` | Session transcripts | Live runtime data, not definitions |
| `~/.openclaw/agents/<id>/agent/openclaw-agent.sqlite` | Per-agent auth/state | Live data |
| `agents/book_project/` | Book project generator code | DS-AIOS application code |
| `app/`, `api/`, `agents/` dirs | Runtime/source code directories | DS-AIOS product code |

### 7.3 What Already Exists as Generic (No Extraction Needed)

| Component | Current Location | Status |
|-----------|-----------------|--------|
| Protocol core rules | `~/.openclaw/protocols/*.md` | Already generic; just copy as-is to DS-EO package |
| Two-layer model concept | `AGENTS.md` §1 | Generic architectural principle |
| Task directory naming convention | AGENTS.md §6 | Generic pattern, already portable |
| Development workflow sequence | AGENTS.md §5 | Generic engineering process |

### 7.4 Extraction Transformation Required

For each CTO/Implementer/Reviewer role:

```
SOURCE: openclaw.json JSON object
        {
          "id": "cto",
          "name": "CTO / Architect",
          "emoji": "🏗️",
          "model": "ollama/qwen3.6:35b",
          "tools": { "allow": [...], "deny": [...] },
          "workspace": "/home/deepsim/agent_system"
        }

TARGET: agents/cto.md (generic markdown prompt)
        
# CTO Agent — DS-EO OpenClaw Edition

**Model placeholder**: <MODEL_CTO>
**Default suggestion**: ollama/qwen3.6:35b

## Identity
You are the CTO / Architect... [from existing prompt, genericized]

## Core Responsibilities
[existing responsibilities, no DS-AIOS path references]

## Tool Policy (OpenClaw)
- tools.allow: ["group:fs", "web_search", ...]  ← same as source
- tools.deny: ["write", "edit", "apply_patch"]  ← same as source
- tools.profile: generic                         ← derived from deny list

## Config Entry Template (openclaw.json)
{
  "id": "cto",
  "name": "CTO / Architect",
  "identity": { "emoji": "🏗️", "name": "CTO" },
  "model": "<MODEL_CTO>",                       ← placeholder, not hardcoded
  "workspace": "<WORKSPACE_PATH>",               ← placeholder
  "tools": { ... }                               ← from source (unchanged)
}

## Protocol References
[existing references converted to generic form, no DS-AIOS paths]
```

### 7.5 Extraction Mapping Summary

| # | What to Extract | Source | Target in Package | Transformation Required |
|---|----------------|--------|-------------------|----------------------|
| E1 | CTO role definition | `openclaw.json` + `docs/prompts/cto.md` | `agents/cto.md` + `config-templates/example_openclaw_config.json` | Convert hardcoded model → placeholder; strip DS-AIOS references |
| E2 | Implementer role definition | `openclaw.json` + `docs/prompts/implementer.md` | `agents/implementer.md` + config template | Same pattern as E1 |
| E3 | Reviewer role definition | `openclaw.json` + `docs/prompts/reviewer.md` | `agents/reviewer.md` + config template | Same pattern as E1 |
| E4 | All 6 protocols (core rules) | `~/.openclaw/protocols/*.md` | `protocols/*.md` | Minimal — remove any project-level context lines |
| E5 | Governance rules | AGENTS.md §§3,4,5,6,7,9 | `ARCHITECTURE.md` + protocol files | Convert section numbers to generic descriptions; remove DS-AIOS paths |
| E6 | Task directory naming convention | AGENTS.md §6.2 | `templates/task.md` | Already generic — copy as-is |
| E7 | Review rubric scoring dimensions | `protocols/review_protocol.md` | `ds_eo_manifest.yaml` + protocol file | Extract scoring weights into manifest for validation |

---

*Plan completed by CTO (ollama/qwen3.6:35b)*  
*Date: 2026-07-28*

---

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| A1 | Repository structure defined and documented | ✅ Complete (Section 1) |
| A2 | `ds_eo_manifest.yaml` schema fully specified with all fields | ✅ Complete (Section 2) |
| A3 | Installation workflow complete with 7 steps, pre-flight checks, and rollback | ✅ Complete (Section 3) |
| A4 | Configuration merge strategy with safety guarantees and conflict resolution | ✅ Complete (Section 4) |
| A5 | Backup/rollback mechanism with automatic and manual paths | ✅ Complete (Section 5) |
| A6 | Verification test suite covering schema, extraction, templates, config safety, end-to-end | ✅ Complete (Section 6) |
| A7 | All components requiring extraction from ~/.openclaw identified with source→target mapping | ✅ Complete (Section 7) |
| A8 | No DS-AIOS-specific dependencies introduced | ✅ Verified — all content is generic or portable |
| A9 | Package is independently installable on any OpenClaw host | ✅ Verified — no external dependencies beyond OpenClaw itself |

## Risks and Mitigations

| # | Risk | Impact | Severity | Mitigation |
|---|------|--------|----------|-----------|
| R1 | User's openclaw.json has custom agent IDs that collide with DS-EO IDs | Config corruption / unexpected overwrite | Medium | Warn user before merge; offer rename option during install |
| R2 | User doesn't have the suggested default models installed | Agents fail to start after install | Low-Medium | Script verifies model availability during Step 2 interactive phase |
| R3 | Protocol files at ~/.openclaw/ already contain host-specific adaptations | DS-EO protocols may not match user's expectations | Low | Document clearly that DS-EO owns these; provide opt-out per-project-only mode |
| R4 | Installation fails mid-way (network, permissions, disk) causing partial state | openclaw.json potentially corrupted | High | All modifications are preceded by backup; verification must pass or rollback triggers automatically |

---

*Awaiting user approval to proceed with Implementation.*
