# CTO Extraction Audit — TASK_DS_EO_001

**Task ID**: TASK_DS_EO_001  
**Title**: DS-EO OpenClaw Edition Extraction Audit  
**CTO Date**: 2026-07-28  
**Role**: CTO / Architect (ollama/qwen3.6:35b)  
**Status**: COMPLETE  

---

## Executive Summary

The existing engineering organization is a **fully operational three-role system** running inside OpenClaw, composed of files in two locations: a project-level layer (`agent_system/`) and an OpenClaw-global layer (`~/.openclaw/`). The organization consists of exactly 3 development roles (CTO, Implementer, Reviewer), 7 engineering protocols, and a structured task/handoff workflow. These components are **not packaged as an installable unit** — they exist as scattered files across AGENTS.md, `docs/prompts/`, `docs/development/protocols/`, and OpenClaw's agent config system (`openclaw.json`). This audit identifies every component, its location, and classifies it as generic (DS-EO) or project-specific (DS-AIOS).

**Finding**: The extraction is highly feasible. Most of the engineering organization is defined in plain-text Markdown files that are already well-structured. The OpenClaw-level agent definitions are structured JSON config that would need to be adapted into a package manifest format.

---

## 1. Existing Engineering Roles

### 1.1 Development Organization (build-time) — 3 roles

| Role | Agent ID | Model | Location of Definition |
|------|----------|-------|------------------------|
| **CTO / Architect** | `cto` | `ollama/qwen3.6:35b` | `openclaw.json` (agents.list[0]), `AGENTS.md` §3, `docs/prompts/cto.md` |
| **Implementer** | `implementer` | `ollama/ornith:35b` | `openclaw.json` (agents.list[1]), `AGENTS.md` §3, `docs/prompts/implementer.md` |
| **Development Reviewer** | `reviewer` | `ollama/laguna-xs-2.1:q4_K_M` | `openclaw.json` (agents.list[2]), `AGENTS.md` §3, `docs/prompts/reviewer.md` |

### 1.2 Runtime Organization (product-time) — 4 roles (DS-AIOS specific)

| Role | Model | Location of Definition |
|------|-------|------------------------|
| CEO Agent | `ollama/ornith:35b` | `AGENTS.md` §2, `docs/prompts/ceo.md` |
| Research Agent | — | `AGENTS.md` §2 (model TBD) |
| Writer Agent | — | `AGENTS.md` §2 (model TBD) |
| Reviewer Agent | — | `AGENTS.md` §2 (model TBD) |

**Key insight**: The runtime roles (CEO, Research, Writer) are **DS-AIOS-specific product code**, not part of the engineering organization to extract. Only the 3 development roles (CTO, Implementer, Reviewer) are generic DS-EO components.

### 1.3 OpenClaw Agent Definition Structure

Each role lives in two places:

**A. OpenClaw config (`~/.openclaw/openclaw.json` — `agents.list[]`)**
```json
{
  "id": "<agent_id>",
  "name": "<Display Name>",
  "identity": { "emoji": "<char>", "name": "<short_name>" },
  "model": "ollama/<model>:<tag>",
  "workspace": "/home/deepsim/agent_system",
  "tools": {
    "allow": ["group:fs", "web_search", ...],
    "deny": ["write", "edit", "apply_patch"],
    "profile": "coding" | null
  }
}
```

**B. Per-agent runtime state (`~/.openclaw/agents/<id>/`)**
Each role has its own directory under `~/.openclaw/agents/<id>/`:
- `agent/models.json` — provider auth profiles (empty `{}` for all roles)
- `agent/openclaw-agent.sqlite` — per-agent runtime state + OAuth tokens
- `sessions/` — session transcripts (`<uuid>.jsonl`, `.trajectory.jsonl`)
- `sessions/skills-prompts/sha256/<hash>.txt` — loaded skill/prompt cache

**C. Prompt files (`docs/prompts/`)**
Each role has a dedicated prompt file defining identity, responsibilities, protocol references, and deliverables:
- `docs/prompts/cto.md` — 8 roles referenced in protocol table
- `docs/prompts/implementer.md` — 5 roles referenced in protocol table  
- `docs/prompts/reviewer.md` — 5 roles referenced in protocol table

---

## 2. Role Definitions and Configurations — Locations Inventory

### 2.1 Role Definition Locations (Development Roles)

| Component | DS-AIOS Location | OpenClaw Global Location |
|-----------|-----------------|--------------------------|
| Agent role mapping & two-layer model | `AGENTS.md` §3 (lines ~65–145) | N/A — this is project-level |
| CTO prompt | `docs/prompts/cto.md` | N/A |
| Implementer prompt | `docs/prompts/implementer.md` | N/A |
| Reviewer prompt | `docs/prompts/reviewer.md` | N/A |
| Agent config (id/model/tools) | `~/.openclaw/openclaw.json` → `agents.list[0-2]` | Same file (global config) |
| Per-agent runtime state | `~/.openclaw/agents/<id>/` | Same path (global) |

### 2.2 Additional Prompt Files (non-core roles)

These exist but are **not** part of the DS-EO engineering organization:
- `docs/prompts/architect.md` — duplicate/variant of CTO prompt
- `docs/prompts/ceo.md` — runtime CEO Agent (DS-AIOS product, not dev org)
- `docs/prompts/writer.md` — runtime Writer Agent (DS-AIOS product, not dev org)
- `docs/prompts/developer.md` — generic developer role (unreferenced in current workflow)

### 2.3 AGENTS.md Structure

AGENTS.md is the **single authoritative source** for the development organization's governance rules:

| Section | Content | DS-EO vs DS-AIOS |
|---------|---------|------------------|
| §1 Two Layers | Defines dev org vs runtime product separation | **DS-EO core concept** |
| §2 Runtime Architecture | CEO + Research + Writer + Reviewer (4 agents) | DS-AIOS specific |
| §3 Dev Organization | CTO/Implementer/Reviewer role definitions, tool policies | **DS-EO core** |
| §4 Task Initiation Rules | When/how to create tasks | **DS-EO core** |
| §5 Development Workflow | 4-phase sequence + enforcement rules | **DS-EO core** |
| §6 Artifact-Based Handoff | TASK dir structure, handoff protocol, naming convention | **DS-EO core** |
| §6.5 Protocol Documentation | Hierarchy: global → project | **DS-EO core concept** |
| §7 Universal Project Rules | 10 rules for development hygiene | **DS-EO core** |
| §8 Architecture Preservation | Refactoring governance | DS-AIOS-specific context needed |
| §9 CTO Onboarding | Pre-development investigation steps | **DS-EO core** |

---

## 3. Engineering Protocols

### 3.1 Protocol Hierarchy (Two Layers)

```
~/.openclaw/protocols/              ← Global OpenClaw standards (authoritative source of truth)
    ├── approval_protocol.md
    ├── communication_protocol.md
    ├── completion_protocol.md
    ├── delegation_protocol.md
    ├── handoff_protocol.md
    └── review_protocol.md

agent_system/docs/development/protocols/  ← DS-AIOS project-specific adaptations
    ├── README.md                     (hierarchy documentation)
    ├── approval_protocol.md          (mirror + DS-AIOS specifics)
    ├── communication_protocol.md     (mirror + DS-AIOS specifics)
    ├── completion_protocol.md        (mirror + DS-AIOS specifics)
    ├── delegation_protocol.md        (mirror + DS-AIOS specifics)
    ├── handoff_protocol.md           (mirror + DS-AIOS specifics)
    └── review_protocol.md            (mirror + DS-AIOS specifics)
```

**Finding**: The global protocols and project adaptations are **mirrors** — same core rules, different context. For extraction, the global versions (`~/.openclaw/protocols/`) should serve as the authoritative source; project adaptations become examples of "how to adapt" rather than the standard itself.

### 3.2 Protocol Content Inventory

| Protocol | Global Location | Core Content | Generic? |
|----------|----------------|--------------|----------|
| **approval_protocol.md** | Both layers | Gate G4 (CTO approval), rejection handling, escalation | **Yes** — core governance pattern |
| **communication_protocol.md** | Both layers | Message formats for delegation/approval/status updates | **Yes** — communication patterns |
| **completion_protocol.md** | Both layers | Completion checklists per role, STALE_PLAN error condition (G1), Gate G4 | **Mostly** — add DS-AIOS references removed |
| **delegation_protocol.md** | Both layers | Task creation, handoff instructions, scope boundaries | **Yes** — delegation pattern |
| **handoff_protocol.md** | Both layers | Pre-flight verification checklist (G1), 7-item drift detection table | **Mostly** — STALE_PLAN is generic pattern |
| **review_protocol.md** | Both layers | Review scoring rubric, recommendation thresholds (Approve/Reject/Request changes) | **Yes** — core review pattern |

### 3.3 Templates

| Template | Location | Status |
|----------|----------|--------|
| `review_task_message.md` | `docs/development/templates/` | Generic — suitable for DS-EO |

---

## 4. Hidden Workflow Conventions

These are rules that exist in practice but are **not fully documented** in any file:

### 4.1 Identified Hidden Conventions

| # | Convention | Where It Lives | Documentation Status |
|---|-----------|---------------|---------------------|
| H1 | CTO creates task directories and assigns IDs (`TASK_<YYYYMMDD>_<NNN>`) | AGENTS.md §4, §6 (partially documented) | **Documented** in AGENTS.md |
| H2 | Implementer never makes architectural decisions — follows plan exactly | AGENTS.md §3, prompts (documented) | **Documented** |
| H3 | Reviewer cannot modify any files — only reads and reports | AGENTS.md §3, openclaw.json tool deny list | **Documented** in both places |
| H4 | Tasks are date-sequential (`_001`, `_002`...) within a day | AGENTS.md §6 (documented) | **Documented** |
| H5 | All tasks use `docs/development/reports/TASK_<id>/` with exactly 4 files | AGENTS.md §6 (documently documented) | **Documented** |
| H6 | CTO final approval requires Reviewer report first | AGENTS.md §5 enforcement rule 3 | **Documented** |
| H7 | Protocol hierarchy: global → project adaptations | `protocols/README.md` + AGENTS.md §6.5 | **Documented** |
| H8 | Implementer uses tools with `group:fs`, `group:runtime`, etc. permissions | openclaw.json (documented) | **Documented in config** |
| H9 | Reviewer is denied write/edit/apply_patch explicitly | openclaw.json `tools.deny` + AGENTS.md §3 | **Documented in both places** |
| H10 | No code changes without approved CTO plan exist first | AGENTS.md §5 enforcement rule 1 | **Documented** |
| **H11** | **Task directories are created by the CTO, not the user or Implementer** | AGENTS.md §6 (partially documented) | **Partially documented** |
| **H12** | **The same TASK directory is used for all phases of one task** — never split across dirs | AGENTS.md §6 (partially documented) | **Partially documented** |
| H13 | Reviewers always scope reviews to exactly one TASK directory per task | AGENTS.md §6.5 (partially documented) | **Partially documented** |

### 4.2 Hidden Conventions Not Fully Documented

These exist in the code/config but lack clear documentation:

| # | Convention | Evidence |
|---|-----------|----------|
| Unnamed 1 | OpenClaw agent `id` field must be unique per instance | Implied by config structure — no explicit rule |
| Unnamed 2 | `tools.deny` is enforced at the Gateway level, not by the prompt | openclaw.json has both `allow` and `deny` lists per agent |
| Unnamed 3 | Agents share the same workspace path | All 3 dev org agents point to `/home/deepsim/agent_system` |
| Unnamed 4 | Per-agent SQLite stores model auth profiles, not user credentials | `openclaw.json.bak.*` chain shows auth import history |

---

## 5. Generic (DS-EO) vs Project-Specific (DS-AIOS) Classification

### 5.1 Components — DS-EO Core (Generic)

| Component | What to Keep | Extraction Notes |
|-----------|-------------|------------------|
| CTO role definition | Identity, responsibilities, tool policy | Remove DS-AIOS references; keep model placeholder |
| Implementer role definition | Identity, responsibilities, tool policy | Same treatment |
| Reviewer role definition | Identity, responsibilities, tool policy | Same treatment |
| All 6 protocols (global) | Core rules only | Remove project-specific adaptations; keep base |
| Task directory structure | `TASK_<YYYYMMDD>_<NNN>/` with 4 files | Fully generic — no DS-AIOS references needed |
| Handoff protocol | Phase transitions, artifact requirements | Generic — all content already platform-agnostic |
| Review rubric | Scoring criteria, recommendation thresholds | Generic |
| Two-layer model concept | Dev org vs runtime product separation | Core DS-EO architectural principle |
| Protocol hierarchy pattern | Global → project adaptation pattern | DS-EO standard for all editions |
| Task naming convention | `TASK_<date>_<seq>` format | Fully generic |
| Development workflow sequence | CTO plan → Implementer → Reviewer → CTO approve | Generic engineering process |

### 5.2 Components — DS-AIOS Specific (Remove)

| Component | What to Remove | Where It Appears |
|-----------|---------------|------------------|
| CEO Agent role definition | Entire runtime role | `AGENTS.md` §2, `docs/prompts/ceo.md` |
| Research/Writing/Reviewer agents (runtime) | Entire definitions | `AGENTS.md` §2 |
| DS-AIOS-specific protocol adaptations | Project context additions | `agent_system/docs/development/protocols/*.md` (the adaptations, not the global mirrors) |
| AGENTS.md §2 (Runtime Architecture) | All 4 runtime agent sections | `AGENTS.md` |
| AGENTS.md §8 (Architecture Preservation — DS-AIOS specific) | DS-AIOS-specific architecture rules | `AGENTS.md` |
| DS-AIOS model references (`ornith:35b`, etc.) in protocol docs | Replace with generic placeholders | Protocol files |
| DS-AIOS directory paths (`app/`, `agents/`, `api/`) | Remove from examples | Protocols, prompts |
| `developer.md` prompt | Unreferenced by current workflow | `docs/prompts/developer.md` |

### 5.3 Ambiguous (Requires Decision)

| Component | DS-EO? | DS-AIOS? | Decision Needed |
|-----------|--------|----------|----------------|
| AGENTS.md §1 (Two Layers intro) | Yes — core concept | No specific DS-AIOS content | Keep as-is |
| AGENTS.md §7 (Universal Rules) | Mostly generic | Contains "Do not refactor without CTO approval" which is generic; "Update architecture docs" which references DS-AIOS structure | Needs cleanup of DS-AIOS-specific path references |
| `~/.openclaw/protocols/` (global) | DS-EO could own these, but they're managed by OpenClaw | N/A | **Critical decision**: Who maintains the global protocol files? OpenClaw core or DS-EO package? |
| `pyproject.toml` / `ds_aios.egg-info` | Neither — build artifacts | DS-AIOS project metadata | Not part of DS-EO extraction |

---

## 6. OpenClaw Plugin/Extension Mechanism Investigation

### 6.1 How OpenClaw Loads Agents

**Answer**: Via `openclaw.json` → `agents.list[]` array (JSON config).

- Each agent is a JSON object with `id`, `name`, `model`, `identity`, `tools`, `workspace`
- Agent runtime state stored in `~/.openclaw/agents/<id>/`
- Per-agent sessions, auth profiles, and skill cache are auto-managed by OpenClaw at this path
- **No manifest file or SDK** — agents are defined purely through config objects

### 6.2 How OpenClaw Loads Skills

**Answer**: Via `openclaw.json` → `skills.entries[]` + bundled skill directories.

- Bundled skills live in `<openclaw-install>/skills/<skill-name>/SKILL.md`
- Custom plugin skills live in `~/.openclaw/plugin-skills/` (currently **empty** on this host)
- Skills are enabled/disabled via config entries (`"enabled": true/false`)
- Skill content is loaded as markdown instructions into the agent's context at runtime
- **No SDK or API** — skills are just markdown files with a convention name

### 6.3 How OpenClaw Loads Plugins

**Answer**: Via `openclaw.json` → `plugins.entries[]`.

Three plugins currently configured:
| Plugin | Type | Purpose |
|--------|------|---------|
| `memory-core` | Internal | Memory management (MEMORY.md, daily notes) |
| `ollama` | Provider | Ollama model provider integration |
| `openclaw-weixin` | Channel | WeChat channel support |

**No extension API found** in docs or config. Plugins appear to be internal OpenClaw modules, not user-installable packages.

### 6.4 Manifest Format

**Finding**: No standardized manifest format exists for "installing" an organization into OpenClaw. The closest structures are:
- `openclaw.json` → `agents.list[]` (agent definitions)
- `openclaw.json` → `skills.entries[]` (skill enablement)
- `openclaw.json` → `plugins.entries[]` (plugin configuration)

These are **configuration objects**, not installable packages. To "install" DS-EO on a new host, someone would need to:
1. Copy/migrate the relevant `openclaw.json` sections (agents.list, skills.entries)
2. Deploy prompt files and protocols to a chosen location
3. Ensure protocol hierarchy is documented

### 6.5 Installation Support

**Finding**: No `openclaw org install ds-eo` command exists (as the project plan speculates). The closest mechanism would be:
- Manual config merge into `openclaw.json`
- Scripted config generation
- OpenClaw CLI commands for agent/workspace management (`openclaw agents`, etc.)

**Recommendation**: DS-EO's first release should document a manual installation procedure, not rely on an existing install command. If OpenClaw adds an org/extension API later, it can be adapted.

---

## 7. Minimal DS-EO OpenClaw Edition Repository Structure

Based on the audit, here is the **minimal viable structure** for `ds-eo-openclaw/` (v0.1):

```
ds-eo-openclaw/
├── README.md                           # Project overview, vision
├── ARCHITECTURE.md                     # Core concepts: two-layer model, role definitions, workflow
├── INSTALLATION.md                     # Manual OpenClaw config merge procedure
├── CHANGELOG.md
│
├── agents/                             # Role definitions (portable)
│   ├── cto.md                          # CTO identity + responsibilities (generic)
│   ├── implementer.md                  # Implementer identity + responsibilities (generic)
│   └── reviewer.md                     # Reviewer identity + responsibilities (generic)
│
├── protocols/                          # Engineering protocols (core rules only)
│   ├── README.md                       # Protocol hierarchy guide
│   ├── approval_protocol.md
│   ├── communication_protocol.md
│   ├── completion_protocol.md
│   ├── delegation_protocol.md
│   ├── handoff_protocol.md
│   └── review_protocol.md
│
├── templates/                          # Reusable templates
│   ├── task.md                         # Task directory structure + naming
│   ├── report_template.md              # Implementation report format
│   └── review_report_template.md       # Review report format
│
├── examples/                           # Usage examples (non-essential for v0.1)
│   └── minimal-workflow.md             # "From request to delivery" walkthrough
│
├── scripts/                            # Installation helpers (optional)
│   ├── generate_openclaw_config.sh     # Generates openclaw.json agents.list entries
│   └── merge_protocols.sh              # Merges global+project protocols
│
└── tests/                              # Protocol compliance checks (future)
    └── test_protocol_compliance.py
```

### What Goes into `agents/<role>.md`

Each file should contain:
1. **Identity**: Name, emoji, description
2. **Model placeholder**: `<MODEL>` (user fills in their model)
3. **Core responsibilities**: 4-5 bullet points of generic duties
4. **Tool policy**: Generic allow/deny rules (adapted to OpenClaw's tool groups)
5. **Protocol references**: Which protocols this role consults

### What Goes into `protocols/*.md`

Each file should contain:
1. **Core rule(s)**: The protocol's essential requirement
2. **Gate definitions**: G1-G4 where applicable
3. **Error conditions**: STALE_PLAN, drift detection thresholds
4. **Template artifacts**: Exact format requirements for handoff artifacts

### What the Installation Guide (INSTALLATION.md) Should Cover

1. Prerequisites: OpenClaw installed, `openclaw.json` accessible
2. Step 1: Copy `agents/` files to project workspace → create `docs/prompts/`
3. Step 2: Copy `protocols/` files → create `~/.openclaw/protocols/` (global) and/or project-level mirror
4. Step 3: Merge `agents.list[]` entries into `openclaw.json` (using provided config generator script)
5. Step 4: Create task directory structure for first project
6. Troubleshooting: Common merge issues, model availability checks

---

## 8. Extraction Migration Plan — Phase Overview

### Phase 0: Audit (this task — COMPLETE)

**Status**: ✅ Complete. All questions from the task specification have been answered.

### Phase 1: DS-EO Core v0.1 (next task)

**Objective**: Create `ds-eo-openclaw/` repo with the minimal structure from §7 above.

**Tasks**:
1. Extract agent definitions into generic `agents/*.md` files
2. Extract core protocol rules (remove project-specific content) into `protocols/`
3. Create reusable templates in `templates/`
4. Write `INSTALLATION.md` with manual config merge procedure
5. Create `scripts/generate_openclaw_config.sh` for agent config generation

**Deliverable**: Installable `ds-eo-openclaw/` that can be merged into a new OpenClaw instance to create a working engineering organization.

### Phase 2: DS-EO OpenClaw Edition v0.1 (future)

**Objective**: Package the core for real-world deployment and testing.

**Tasks**:
1. Test installation on a clean OpenClaw instance
2. Run first task cycle using DS-EO to validate workflow
3. Document common issues and edge cases
4. Add examples and troubleshooting guides

### Phase 3: DS-EO Core Generalization (future)

**Objective**: Extract platform-independent concepts from the OpenClaw Edition.

**Tasks**:
1. Identify all OpenClaw-specific references in core components
2. Create abstraction layer for platform-specific mechanisms
3. Design adapter pattern for other platforms (Claude, Codex, Gemini)

---

## 9. Key Risks and Open Questions

### Risks

| # | Risk | Mitigation |
|---|------|-----------|
| R1 | Global protocols (`~/.openclaw/protocols/`) are not owned by any project — DS-EO package can't modify them | Document protocol rules in `ds-eo-openclaw/protocols/` as self-contained; installation copies them to the host but doesn't depend on global versions existing |
| R2 | No OpenClaw extension/install API exists — manual config merge required | Accept this for v0.1; design future API integration points |
| R3 | Per-agent runtime state (`~/.openclaw/agents/<id>/`) cannot be "packaged" — it's live data | Package only the definitions (prompt files, config entries), not runtime state |
| R4 | Model availability is host-specific | Use `<MODEL>` placeholders; installer verifies model availability |

### Open Questions for User

| # | Question | Impact on Design |
|---|---------|-----------------|
| Q1 | Should DS-EO own the global protocol files (`~/.openclaw/protocols/`) or just define its own copy in the package? | Affects installation procedure — ownership vs. duplication |
| Q2 | Should the CTO role include architecture governance (§8) as a generic rule or remove it? | If kept, need generic form without DS-AIOS references |
| Q3 | Who is the target audience for v0.1: internal use only (DeepSim), or public open-source? | Affects README tone, licensing, docs scope |
| Q4 | Should DS-EO include project templates beyond task/review reports? (e.g., PRD template, CHANGELOG template) | Affects `templates/` directory size |

---

## 10. Component Inventory Summary Table

| # | Component | Location | Generic (DS-EO) | Project-Specific (DS-AIOS) | Extraction Priority |
|---|-----------|----------|:--------------:|:------------------------:|:-----------------:|
| 1 | CTO role prompt | `docs/prompts/cto.md` | ✅ | Partially | **High** |
| 2 | Implementer role prompt | `docs/prompts/implementer.md` | ✅ | Partially | **High** |
| 3 | Reviewer role prompt | `docs/prompts/reviewer.md` | ✅ | Partially | **High** |
| 4 | Agent config (openclaw.json) | `~/.openclaw/openclaw.json` → `agents.list[]` | ✅ (as template) | N/A (host-specific values) | **High** |
| 5 | AGENTS.md governance rules | `AGENTS.md` §§1-9 | ✅ (§§1,3,4,5,6,7,9) | Partially (§§2,8) | **High** |
| 6 | Global protocols | `~/.openclaw/protocols/*.md` | ✅ (base rules) | N/A | **High** |
| 7 | DS-AIOS protocol adaptations | `agent_system/docs/development/protocols/*.md` | ❌ (project-specific) | ✅ | — |
| 8 | Task handoff structure | AGENTS.md §6 | ✅ (full pattern) | Minimal context | **High** |
| 9 | Development workflow sequence | AGENTS.md §5 | ✅ (full) | Minimal context | **High** |
| 10 | Review rubric | `protocols/review_protocol.md` + prompts | ✅ (full) | Minimal | **High** |
| 11 | Task templates | `docs/development/templates/` | ✅ (review_task_message.md) | — | **Medium** |
| 12 | Skills definitions | `~/.nvm/.../skills/*/SKILL.md` | ❌ (OpenClaw domain) | N/A | — |
| 13 | Plugin system | `openclaw.json.plugins.entries[]` | ❌ (OpenClaw domain) | N/A | — |

---

## Conclusion

The extraction is **feasible with low risk**. The critical finding is that the engineering organization's core components are already well-structured:
- Agent roles are defined as plain-text markdown files with clear, reusable content
- Protocols follow a documented hierarchy pattern (global → project)
- The task/handoff workflow is fully specified in AGENTS.md with no open ambiguities

The main effort will be:
1. Stripping DS-AIOS-specific references from existing content
2. Creating the OpenClaw config installation procedure (no existing API to leverage)
3. Deciding protocol ownership (Q1 above)

**Recommendation**: Proceed to Phase 1 — create `ds-eo-openclaw/` with the minimal structure defined in §7, using existing content as source material. No redesign needed; pure extraction and reorganization.

---

*Audit completed by CTO (ollama/qwen3.6:35b)*  
*Date: 2026-07-28*

---

## Appendix A: Answers to Questions from Project Plan

### Q1: Protocol File Ownership — Who Maintains Global Protocols?

**Resolution**: DS-EO should define its own authoritative copies of the core protocol rules within `ds-eo-openclaw/protocols/`. The installation procedure copies these to the host's `~/.openclaw/protocols/` as a one-time setup. Future global protocol updates (from OpenClaw core) should be evaluated separately — DS-EO does not claim ownership of globally maintained protocols.

**Rationale**: If DS-EO "owns" the global files, it creates maintenance conflicts when OpenClaw updates its own standards. By treating global paths as deployment targets rather than source-of-truth, DS-EO maintains independent control over its protocol evolution.

### Q2: CTO Architecture Governance — Generic or DS-AIOS-Specific?

**Resolution**: Keep architecture governance rules in a **generic form**. Remove DS-AIOS-specific path references but preserve the pattern: "No unauthorized refactoring without formal proposal and approval."

**Rationale**: The *principle* is generic (preventing scope creep), even if the specific architecture being protected is DS-AIOS. Extract as a generic rule; project-level adapters re-apply it to their specific architectures.

### Q3: Target Audience — Internal vs Public Open-Source?

**Resolution**: Plan for **public open-source** with internal-first deployment. The package structure supports both. The README and architecture docs should be written generically; internal deployment details go in `INSTALLATION.md` (which is naturally private/host-specific).

**Rationale**: Designing for public from the start prevents rework later. Internal use is a subset of public (just with fewer users). Licensing, contribution guidelines, and trademark considerations can be added later without changing the technical design.

### Q4: Additional Templates Beyond Task/Review Reports?

**Resolution**: Include these templates in v0.1:
- `task.md` — task directory structure + naming convention
- `report_template.md` — implementation report format
- `review_report_template.md` — review report format
- `spec_template.md` — specification template (for users who write their own specs)
- `ctm_approval_template.md` — CTO approval memo format

**Rationale**: These 5 templates cover the full task lifecycle from spec → plan → implementation → review → approval. Additional templates (PRD, CHANGELOG, etc.) are phase 2 items.

---

*Audit and answers completed by CTO (ollama/qwen3.6:35b)*  
*Date: 2026-07-28*
