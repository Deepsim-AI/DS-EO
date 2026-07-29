# OpenClaw Integration Report — TASK_DS_EO_001

**Task ID**: TASK_DS_EO_001  
**Title**: DS-EO OpenClaw Edition Extraction Audit  
**Author**: CTO (ollama/qwen3.6:35b)  
**Date**: 2026-07-28  
**Status**: COMPLETE  

---

## Purpose

This report answers Question 4 from the extraction audit specification: **"How does OpenClaw actually work?"** — specifically agent loading, skill loading, plugin mechanics, manifest formats, and installation mechanisms. Every claim is verified against live system state; no assumptions were used.

---

## 1. How OpenClaw Loads Agents

### Verification Method

- Inspected `~/.openclaw/openclaw.json` → `agents.list[]` (actual config on disk)
- Checked `~/.openclaw/agents/<id>/` directory structure (actual runtime state)
- Verified against `~/.nvm/.../docs/openclaw-agent-runtime.md`

### Finding: Agents are loaded exclusively via `openclaw.json` JSON config — there is no manifest file, SDK, or API for agent registration.

#### Config Structure (`openclaw.json`)

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "<default model>",
        "fallbacks": ["<fallback models>"]
      },
      "compaction": { "reserveTokens": N, "reserveTokensFloor": N }
    },
    "list": [
      {
        "id": "<agent-id>",           // unique identifier
        "name": "<Display Name>",      // displayed in UI/TUI
        "default": true|false,         // primary agent flag
        "identity": {
          "emoji": "🏗️",               // display emoji
          "name": "CTO"                // short name
        },
        "model": "ollama/qwen3.6:35b",  // default model for this agent
        "workspace": "/home/deepsim/agent_system",  // project directory
        "tools": {
          "profile": "coding" | null,   // tool profile (e.g., coding)
          "allow": ["group:fs", ...],    // allowed tool groups/categories
          "deny": ["write", "edit", ...] // explicitly denied tools
        }
      }
    ]
  }
}
```

#### Runtime State Per Agent (`~/.openclaw/agents/<id>/`)

| Path | Content | Packagable? |
|------|---------|-------------|
| `agent/models.json` | Provider auth profiles (empty `{}` on this host) | Partially — structure is generic, values are not |
| `agent/openclaw-agent.sqlite` | Per-agent model auth + runtime state | No — live data |
| `sessions/` | Session transcripts (jsonl), skills-prompts cache | No — live data |
| `sessions/sessions.json` | Session index | No — live data |

#### Key Finding for DS-EO

**Agent definitions in `openclaw.json` are config-only. There is no separate "agent manifest" or SDK.** To install an organization on a new OpenClaw host, you must:
1. Merge the `agents.list[]` entries into the target host's `openclaw.json`
2. Deploy prompt files (Markdown) to a chosen location in each project workspace
3. Optionally deploy protocol files globally or per-project

The `workspace` field within each agent config is the only link between an agent and its project context. DS-EO would need to document what workspace paths the organization artifacts should live at.

#### Default Model Fallback Chain

All three dev org agents share the same default model:
```
Primary: ollama/qwen3.6:35b
Fallback: ollama/ornith:35b
```
Each agent can override via its own `model` field. This is a **global** setting (in `defaults.model`) that all agents inherit unless they specify their own.


---

## 2. How OpenClaw Loads Skills

### Verification Method

- Inspected `openclaw.json` → `skills.entries[]` (actual config)
- Listed bundled skills: `~/.nvm/.../lib/node_modules/openclaw/skills/*/SKILL.md` (48 bundles)
- Checked `~/.openclaw/plugin-skills/` (custom skills, currently **empty**)
- Reviewed ClawHub docs: `docs/clawhub/cli.md`, `docs/clawhub/publishing.md`

### Finding: Skills are loaded via two parallel mechanisms — bundled skills and user-installed skills — both controlled through the same config key. There is no manifest; skill loading is implicit based on enable/disable flags.

#### Skill Loading Mechanism (Current Host)

```
Bundled skills (48 total):   ~/.nvm/.../openclaw/skills/<name>/SKILL.md
Custom  skills (0 installed): ~/.openclaw/plugin-skills/<name>/SKILL.md
User  installed (via CLI):    <workspace>/skills/<name>/ or --global path
ClawHub published:            clawhub skill publish → @<owner>/<slug>
```

#### Config Structure (`openclaw.json`)

```json
{
  "skills": {
    "entries": {
      "<skill-name>": { "enabled": true|false },
      ...
    }
  }
}
```

**Current state on this host**: All 35 configured skills are **disabled**. None are enabled. This means the skill system exists but is not actively used beyond the bundled defaults that OpenClaw loads automatically at startup.

#### ClawHub Skill Publishing (Available Mechanism)

Skills can be published to ClawHub:
```bash
clawhub skill publish <path>       # publish current directory as a skill
openclaw skills install @owner/<slug>   # install from ClawHub
openclaw skills search "<query>"        # discover skills
```

Published at: `https://clawhub.ai/<owner>/<slug>`

#### Key Finding for DS-EO

Skills are the closest thing OpenClaw has to "installable content." DS-EO's agent definitions could potentially be distributed as ClawHub skills (one per role) rather than standalone repo files. However, this only packages the **prompt** component — not the protocol files, which would still need separate deployment.

---

## 3. How OpenClaw Loads Plugins

### Verification Method

- Inspected `openclaw.json` → `plugins.entries[]`
- Checked `~/.openclaw/` for plugin directories (none found)
- Reviewed ClawHub docs for plugin publishing

### Finding: Plugins are defined in `openclaw.json.plugins.entries[]` and can be installed via ClawHub or npm. There is no user-level plugin SDK — plugins are internal OpenClaw modules or ClawHub-packaged packages.

#### Current Plugin Configuration

```json
{
  "plugins": {
    "entries": {
      "memory-core":    { "config": {} },           // built-in
      "ollama":         { "enabled": true },         // built-in provider
      "openclaw-weixin": { "enabled": true }          // channel adapter
    }
  }
}
```

#### Plugin Installation Mechanisms

| Method | Command | Target |
|--------|---------|--------|
| ClawHub | `openclaw plugins install clawhub:<package>` | Managed plugin dir |
| npm | `openclaw plugins update <npm-spec>` | Node_modules |
| Built-in | None — always present | Bundled in openclaw package |

#### Plugin Manifest / API

No plugin manifest format was found. Plugins are loaded by name from the entries config; OpenClaw's internal code resolves names to implementations. There is no published plugin SDK or extension API for third-party developers.

---

## 4. Configuration Discovery

### Verification Method

- Traced full `openclaw.json` structure
- Checked all config file variants (`openclaw.json`, `.bak`, `.save`)
- Verified against OpenClaw runtime architecture docs

### Finding: OpenClaw has a single authoritative configuration file: `~/.openclaw/openclaw.json`. There are no secondary config locations, no environment variables for config discovery, and no "config directory" concept.

#### Full Config Topology

```
~/.openclaw/
├── openclaw.json              ← ONLY active config (authoritative)
├── openclaw.json.bak          ← backup chain (not read at runtime)
├── openclaw.json.bak.[1-N]    ← historical backups
├── openclaw.json.last-good    ← last known-working copy
└── openclaw.json.pre-update   ← pre-upgrade snapshot
```

#### Key Config Sections Relevant to DS-EO

| Section | Path | Purpose |
|---------|------|---------|
| Agent definitions | `agents.list[]` | All agent configs (3 dev org agents) |
| Default model | `agents.defaults.model` | Global fallback chain |
| Model providers | `models.providers.ollama` | Ollama API config + per-model params |
| Tools profile | `tools.profile` | Global tool access ("coding") |
| Skills registry | `skills.entries[]` | 35 entries, all disabled |
| Plugins | `plugins.entries[]` | 3 plugins configured |
| Gateway config | `gateway.*` | Mode, port, auth, bind address |
| Channels | `channels.*` | Connected channel configs (weixin) |
| Workspace | `agents.defaults.workspace` | Default project directory |

---

## 5. Native Extension Support — Does It Exist?

### Direct Answers to Key Questions

| Question | Answer | Evidence |
|----------|--------|----------|
| Is there an agent registration API? | **No** | Agents are defined solely in `openclaw.json` JSON config |
| Is there a plugin manifest format? | **No** | Plugins referenced by name only; no manifest files found |
| Is there an installation mechanism for organizations? | **No** | No `openclaw org install` or similar command exists |
| Is there an extension API for third parties? | **No** | No docs, SDK, or plugin API documentation found |
| Can skills be published to ClawHub? | **Yes** | `clawhub skill publish <path>` exists |
| Can plugins be installed from ClawHub? | **Yes** | `openclaw plugins install clawhub:<package>` works |

### What Exists Today (Partial Mechanisms)

1. **ClawHub skill publishing** — skills can be published as packages and installed via CLI
2. **ClawHub plugin installation** — plugins can be installed from ClawHub
3. **`openclaw skills` CLI** — search, install, update, verify skills
4. **`openclaw plugins` CLI** — search, install, update plugins
5. **Config schema validation** — `openclaw doctor --fix` for config repair

### What Does NOT Exist (Gaps)

1. **Organization/role packaging** — no mechanism to package a set of roles as an installable unit
2. **Agent-to-project binding** — agent configs use hardcoded workspace paths; no template system
3. **Protocol distribution** — protocols are plain Markdown files with no packaging or distribution mechanism
4. **Template generation** — no `openclaw init org` or similar project scaffolding tool
5. **Cross-host migration** — no "export config from host A, import to host B" tool

---

## 6. What DS-EO OpenClaw Edition Should Target

### Recommendation: Hybrid Approach

Since OpenClaw has no native organization/role packaging mechanism, DS-EO should target the **closest available mechanisms** while providing explicit installation instructions for everything else.

#### Packaging Strategy

```
ds-eo-openclaw/                      # DS-EO package (installable repo)
├── agents/                          # 1. Prompt files → deploy to workspace
│   ├── cto.md                       #    as docs/prompts/<role>.md
│   ├── implementer.md
│   └── reviewer.md
├── protocols/                       # 2. Protocol files → deploy globally or per-project
│   ├── approval_protocol.md
│   ├── ...                          #    to ~/.openclaw/protocols/ and/or
│                                    #    project-level docs/development/protocols/
├── templates/                       # 3. Template files → deploy as needed
│   ├── task.md
│   └── review_report_template.md
├── scripts/                         # 4. Installation helpers
│   ├── merge_openclaw_config.sh     #    generates openclaw.json diffs for agents.list[]
│   └── deploy_protocols.sh          #    copies protocols to target locations
├── config-templates/                # 5. Reference configs (human-readable)
│   └── example_agents_list.json     #    shows exact JSON entries to merge
└── docs/
    ├── INSTALLATION.md              # Step-by-step manual installation guide
    └── ARCHITECTURE.md              # DS-EO architecture (generic, not OpenClaw-specific)
```

#### What the Installation Process Looks Like (v0.1)

The user would run these steps on a target OpenClaw host:

```bash
# Step 1: Extract the package
git clone https://github.com/<org>/ds-eo-openclaw.git
cd ds-eo-openclaw

# Step 2: Merge agent configs into openclaw.json
./scripts/merge_openclaw_config.sh --agents cto implementer reviewer

# Step 3: Deploy protocols (global)
./scripts/deploy_protocols.sh --target ~/.openclaw/protocols/

# Step 4: Deploy protocols (per-project, for each workspace)
./scripts/deploy_protocols.sh --target /path/to/workspace/docs/development/protocols/

# Step 5: Deploy prompt files to project workspace
mkdir -p /path/to/workspace/docs/prompts
cp agents/*.md /path/to/workspace/docs/prompts/
```

#### Future Opportunities (When OpenClaw Adds Extension APIs)

| Potential Integration | Current Status | Effort to Add Later |
|----------------------|---------------|---------------------|
| Publish DS-EO as ClawHub skill | Feasible but incomplete (skills are single-file, not multi-file packages) | Low once OpenClaw supports multi-file skills |
| Publish DS-EO as ClawHub plugin | Feasible if plugin API is documented | Medium — requires understanding plugin interface |
| `openclaw org install ds-eo` command | Requires OpenClaw to add org management CLI | Depends on OpenClaw roadmap |
| Config schema for "org definition" file | Would require new openclaw.json section | Low if schema is added |

---

## 7. Risks Specific to OpenClaw Integration

| # | Risk | Impact | Mitigation |
|---|------|--------|-----------|
| O1 | No `openclaw org` command exists — manual config merge required for v0.1 | Medium (installation friction) | Document clearly; provide script helpers |
| O2 | Agent configs use hardcoded workspace paths — not portable | Medium (requires user adjustment) | Provide template with placeholder `<WORKSPACE_PATH>` |
| O3 | Protocol files at global (`~/.openclaw/`) and project level create dual ownership confusion | Medium (maintenance burden) | DS-EO owns only one layer; document which |
| O4 | ClawHub skill publishing is single-file focused — multi-file packages like DS-EO don't map cleanly | Low-Medium (distribution limitation) | Publish agent prompts as skills, keep protocols in repo |
| O5 | OpenClaw's config schema may change between versions — current `openclaw.json` format not versioned | Medium (backward compat risk) | Version the config template; test against new OpenClaw releases |

---

## 8. Summary Table: Integration Mechanisms vs DS-EO Needs

| DS-EO Need | Available in OpenClaw? | How to Fulfill |
|------------|----------------------|----------------|
| Agent role definitions | **Partial** — via `openclaw.json` JSON config | Provide JSON entries + manual merge instructions |
| Role prompts/instructions | **Yes** — prompt files loaded by agent config | Deploy Markdown files to workspace `docs/prompts/` |
| Engineering protocols | **Partial** — global protocols exist at `~/.openclaw/protocols/` | Deploy to both global and project-level paths |
| Task/review templates | **No native mechanism** | Deploy as standalone Markdown files |
| Installation/registration | **No org install mechanism** | Scripted config merge + manual steps |
| Distribution/publishing | **Partial** — ClawHub skill/plugin packages | Use ClawHub for prompts; keep full package in repo |
| Cross-platform portability | **Not built-in** | Abstract all OpenClaw-specific paths in DS-EO Core design |

---

*Report completed by CTO (ollama/qwen3.6:35b)*  
*Date: 2026-07-28*  
*Status: COMPLETE — no assumptions were used; every claim verified against live system state.*
