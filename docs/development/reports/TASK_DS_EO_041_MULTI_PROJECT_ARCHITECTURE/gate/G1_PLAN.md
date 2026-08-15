# Multi-Project Architecture Design for DS-EO

**Task ID:** TASK_DS_EO_041  
**Status:** Design Phase (G1 — Planning)  
**Date:** 2026-08-13  

---

## Problem Statement

DS-EO currently supports exactly **one project per agent identity**. All four agents (CTO, Implementer, Reviewer, PM) share a single hard-coded workspace (`/home/deepsim/ds_eo_openclaw`). This works for DS-EO as a standalone framework, but fails when DS-EO is used to build multiple consumer projects:

- The deepsim-ai-lab website project has its own Git repo, its own task IDs (DAL prefix), its own state
- Every new consumer project would need a new set of agent identities (`cto-dal`, `cto-webshop`, etc.)
- No mechanism exists to route a task to the correct workspace/agent identity
- Task IDs share a single namespace across all projects

---

## Findings: Current Architecture Investigation

### What We Found

| Component | Current Design | Implication |
|-----------|---------------|-------------|
| **OpenClaw agent config** | `agents.list[].workspace` is hard-coded per agent ID | Cannot be overridden at dispatch time; one workspace per identity |
| **Gateway routing** | Bindings route messages → agent by channel/peer, not by project | No concept of "which project" in the gateway |
| **AgentRegistry** | Reads `agents_list.json`; each entry has a single `workspace` field | No multi-workspace support |
| **TaskIntakeManager** | `_dispatchers_base = workspace_root/docs/dispatchers`; `_reports_base = workspace_root/docs/development/reports` | Task directories always under the dispatcher's workspace_root |
| **TaskIDPattern** | `TASK_(\d{8})_\d+` — no project prefix or namespace | All task IDs are global; two projects can collide on same date |
| **WorkflowEngine** | `execute_transition()` accepts `target_agent` string but resolves it from the workflow config, which references agents by ID only | No workspace/project awareness in transitions |
| **SessionSpawnManager** | Writes dispatcher state under `workspace_root/docs/dispatchers/<task_id>/`; uses `session_spawn` tool for real session creation | Session store is global per gateway; workspace only controls file paths, not session identity |
| **WorkflowSupervisor** | `workspace_root` passed at construction time; all path resolution (liveness scans, escalation reports) uses this root | Multi-project requires separate supervisor instances per project |

### What This Means

The DS-EO architecture has **implicit single-project assumption everywhere**: workspace is baked into every component's constructor. There is **no project/workspace abstraction** at the dispatcher layer — only a raw string path.

---

## Design Principles

1. **One DS-EO framework, many consumers** — The framework (`ds_eo_openclaw/`) stays untouched; all extension happens in configuration and thin dispatch layers
2. **Explicit over implicit** — Every task must declare which project it belongs to; no guessing
3. **Isolation boundaries** — Each project has its own: workspace, Git repo, task namespace, artifact directories, supervisor instance, session pool (via agent identity)
4. **Minimal mutation** — The framework's `agents_list.json` stays clean; per-project configs sit in the consumer project's workspace
5. **Discoverability** — A project catalog lets the CTO resolve "which workspace should TASK_X go to?"

---

## Architecture: Project Catalog + Agent Identity Matrix

### Overview Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       Gateway / OpenClaw                      │
│  ┌───────────┐  ┌────────────┐  ┌───────────┐  ┌────────┐  │
│  │ cto       │  │ implementer│  │ reviewer  │  │ pm     │  │
│  │ ds-eo     │  │ ds-eo      │  │ ds-eo     │  │ ds-eo  │  │
│  └───────────┘  └────────────┘  └───────────┘  └────────┘  │
│                                                              │
│  ┌───────────┐  ┌────────────┐  ┌───────────┐  ┌────────┐  │
│  │ cto-dal   │  │ implementer│  │ reviewer- │  │ pm-dal │  │
│  │ dal       │  │ -dal       │  │ reviewer  │  │        │  │
│  └───────────┘  └────────────┘  └───────────┘  └────────┘  │
│                                                              │
│  ┌───────────┐  ... (future projects)                        │
│  │ cto-web   │  ┐                                            │
│  │ -web      │  ┘                                           │
│  └───────────┘                                              │
├─────────────────────────────────────────────────────────────┤
│                      Project Catalog                          │
│                                                             │
│  ~/.openclaw/ds_eo/                                         │
│  ├── projects.yaml        (global project definitions)       │
│  ├── cto                   (framework agent identity)       │
│  ├── implementer           (framework agent identity)       │
│  └── ...                                                   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                   Consumer Projects                           │
│                                                             │
│  /home/deepsim/deepsim-ai-lab/                              │
│  ├── ds_eo_project.yaml     (this project's identity)       │
│  ├── docs/development/reports/         ← DAL task artifacts │
│  └── docs/dispatchers/                      ← DAL state     │
│                                                             │
│  /home/deepsim/another-project/                             │
│  ├── ds_eo_project.yaml                                  │
│  └── ...                                                 │
└─────────────────────────────────────────────────────────────┘
```

### Layer 1: Project Catalog (`~/.openclaw/ds_eo/projects.yaml`)

A global catalog of all projects known to DS-EO. Each project declares:

```yaml
# ~/.openclaw/ds_eo/projects.yaml

projects:
  # ── Framework itself ──
  - name: "ds-eo-framework"
    id: "framework"                    # namespace prefix for task IDs
    workspace: "/home/deepsim/ds_eo_openclaw"
    git_repo: "git@github.com:Deepsim-AI/DS-EO.git"
    task_prefix: "DS_EO"               # TASK_DS_EO_041, TASK_DS_EO_042...
    agent_id_prefix: ""                # no prefix — cto, not cto-framework
    artifact_paths:
      reports: "docs/development/reports"
      dispatchers: "docs/dispatchers"
    default_agents: [cto, implementer, reviewer, pm]

  # ── Deepsim AI Lab Website ──
  - name: "deepsim-ai-lab"
    id: "dal"
    workspace: "/home/deepsim/deepsim-ai-lab"
    git_repo: ""                        # local-only, no remote yet
    task_prefix: "DAL"                  # TASK_DAL_001, TASK_DAL_002...
    agent_id_prefix: "-dal"             # cto-dal, implementer-dal...
    artifact_paths:
      reports: "docs/development/reports"
      dispatchers: "docs/dispatchers"
    default_agents: [cto-dal, implementer-dal, reviewer-dal, pm-dal]

  # ── Future project example ──
  - name: "webshop-backend"
    id: "ws"
    workspace: "/home/deepsim/webshop"
    git_repo: ""
    task_prefix: "WS"
    agent_id_prefix: "-ws"
    artifact_paths:
      reports: "docs/development/reports"
      dispatchers: "docs/dispatchers"
    default_agents: [cto-ws, implementer-ws, reviewer-ws, pm-ws]
```

### Layer 2: Per-Project Identity Manifest (`<workspace>/ds_eo_project.yaml`)

Each consumer project declares how DS-EO agents map to OpenClaw identities:

```yaml
# /home/deepsim/deepsim-ai-lab/ds_eo_project.yaml

project_id: "dal"
project_name: "Deepsim AI Lab Website"
framework_root: "/home/deepsim/ds_eo_openclaw"

agent_mappings:
  - framework_agent: "cto"
    project_agent: "cto-dal"
    model: "ollama/qwen3.6:35b"
    workspace: "/home/deepsim/deepsim-ai-lab"
    tools_allow:
      - "group:fs"
      - "web_search"
      - "web_fetch"
      - "sessions_list"
      - "session_status"
      - "memory_search"
      - "memory_get"
      - "exec"
      - "process"
      - "sessions_spawn"
      - "sessions_send"
    tools_deny: ["write", "edit", "apply_patch"]

  - framework_agent: "implementer"
    project_agent: "implementer-dal"
    model: "ollama/ornith:35b"
    workspace: "/home/deepsim/deepsim-ai-lab"
    tools_allow:
      - "group:fs"
      - "group:runtime"
      - "group:web"
      - "group:sessions"
      - "group:memory"

  - framework_agent: "reviewer"
    project_agent: "reviewer-dal"
    model: "ollama/laguna-xs-2.1:q4_K_M"
    workspace: "/home/deepsim/deepsim-ai-lab"
    tools_allow:
      - "group:fs"
      - "web_search"
      - "web_fetch"
      - "exec"
      - "process"
      - "sessions_list"
      - "session_status"
      - "memory_search"
      - "memory_get"
    tools_deny: ["write", "edit", "apply_patch"]

  - framework_agent: "pm"
    project_agent: "pm-dal"
    model: "ollama/gpt-oss:20b"
    workspace: "/home/deepsim/deepsim-ai-lab"
    tools_allow:
      - "group:fs"
      - "web_search"
      - "web_fetch"
      - "exec"
      - "write"
      - "sessions_list"
      - "session_status"
      - "memory_search"
      - "memory_get"
    tools_deny: ["process", "edit", "apply_patch", "browser", "canvas", "nodes"]

task_id_prefix: "DAL"
```

### Layer 3: Project-Scoped Agent Registry (`agents_project_list.json`)

Each project generates or maintains its own `agents_project_list.json` in its workspace root, combining framework agent configs with project-specific overrides:

```json
[
  {
    "id": "cto-dal",
    "name": "CTO / Architect (dal)",
    "identity": { "emoji": "🏗️", "name": "CTO" },
    "model": "ollama/qwen3.6:35b",
    "workspace": "/home/deepsim/deepsim-ai-lab",
    "tools_allow": [...],
    "tools_deny": [...]
  },
  ...
]
```

This file is **consumed by the dispatcher** (not OpenClaw config directly) — the dispatcher reads it to resolve `target_agent` to a workspace + model during dispatch, then passes those to `session_spawn` with the correct `agentId`.

---

## Isolation Boundaries

| Boundary | Framework Agents | DAL Agents | Future Project Agents |
|----------|-----------------|------------|----------------------|
| **OpenClaw workspace** | `/home/deepsim/ds_eo_openclaw` | `/home/deepsim/deepsim-ai-lab` | project-specific |
| **Task artifacts dir** | `ds_eo_openclaw/docs/development/reports/` | `deepsim-ai-lab/docs/development/reports/` | project-specific |
| **Dispatcher state** | `ds_eo_openclaw/docs/dispatchers/` | `deepsim-ai-lab/docs/dispatchers/` | project-specific |
| **Session store** | CTO/implementer/reviewer/pm sessions (global) | cto-dal, implementer-dal, reviewer-dal, pm-dal sessions (separate agent IDs = separate sessions in OpenClaw) | project-specific agent IDs |
| **Git repository** | `Deepsim-AI/DS-EO` | local only (for now) | project-specific |
| **Task ID namespace** | `TASK_DS_EO_*` | `TASK_DAL_*` | `TASK_<PREFIX>_*` |
| **Supervisor instance** | One WorkflowSupervisor per project, constructed with project's workspace_root | Separate instance at `/home/deepsim/deepsim-ai-lab` | Project-specific |

---

## Dispatcher Enhancement: Project Routing Layer

The dispatcher needs a thin routing layer between the `WorkflowEngine` and `SessionSpawnManager`:

```
┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐
│  CTO Agent   │────▶│  ProjectResolver  │────▶│ SessionSpawnMgr  │
│              │     │                   │     │                  │
│  Receives    │     │  1. Read          │     │  Takes:          │
│  task from   │     │     project_id    │     │  - agent_id      │
│  user/G0     │     │  2. Lookup        │     │  - model         │
│              │     │     in catalog    │     │  - workspace     │
│              │     │  3. Return:       │     │  - task_id       │
│              │     │     target_agent  │     │  - prompt        │
│              │     │     + workspace   │     │                  │
└──────────────┘     └───────────────────┘     └──────────────────┘
```

### New Module: `ds_eo_openclaw/dispatcher/project_resolver.py`

```python
class ProjectResolver:
    """Resolve project → agent identity + workspace for a given task."""
    
    def __init__(self, catalog_path=None):
        # Loads ~/.openclaw/ds_eo/projects.yaml
    
    def resolve_by_task_id(self, task_id: str) -> ProjectInfo:
        """Given TASK_DS_EO_041 → project=framework, target=cto"""
        """Given TASK_DAL_002 → project=dal, target=cto-dal"""
    
    def resolve_by_project_id(self, project_id: str) -> AgentIdentityMatrix:
        """Returns all agent mappings for a project."""
    
    def generate_agent_id(self, role: str, project_id: str) -> str:
        """framework cto + dal suffix → cto-dal"""
    
    def next_task_id(self, project_id: str) -> str:
        """DAL + 2026-08-13 + seq → TASK_DAL_041 (starts fresh per project)"""
```

### Modified TaskIntakeManager

Instead of `_next_task_id()` scanning `docs/dispatchers/` globally, the PM's intake system would:

1. Accept a `project_id` parameter (or auto-detect from workspace root)
2. Use `ProjectResolver.next_task_id(project_id)` to get a project-scoped sequential ID
3. Write task artifacts under `project.workspace/docs/dispatchers/` not framework's path
4. Return the resolved agent IDs for the CTO handoff

### Modified AgentRegistry

The registry would need to merge `agents_list.json` (framework) + `agents_project_list.json` (per-project) into a unified lookup table, keyed by full agent ID (`cto-dal`, not just `dal`).

---

## OpenClaw Config Integration

OpenClaw's `openclaw.json` **cannot** dynamically select workspaces per-task. So we need:

1. **Static bindings:** Register each project's agents as separate OpenClaw identities in `openclaw.json`
   ```json
   {
     "agents": {
       "list": [
         // Framework agents (unchanged)
         { "id": "cto", "workspace": "/home/deepsim/ds_eo_openclaw", ... },
         { "id": "implementer", "workspace": "/home/deepsim/ds_eo_openclaw", ... },
         // DAL agents (new)
         { "id": "cto-dal", "workspace": "/home/deepsim/deepsim-ai-lab", ... },
         { "id": "implementer-dal", "workspace": "/home/deepsim/deepsim-ai-lab", ... },
         { "id": "reviewer-dal", "workspace": "/home/deepsim/deepsim-ai-lab", ... },
         { "id": "pm-dal", "workspace": "/home/deepsim/deepsim-ai-lab", ... },
       ]
     }
   }
   ```

2. **Binding routes (optional):** If you want webchat messages to auto-route:
   ```json
   {
     "bindings": [
       {
         "agentId": "pm-dal",
         "match": { "channel": "webchat", "peer": { "id": "/dal.pm", "kind": "direct" } }
       },
       // ... more routes for other channels/projects
     ]
   }
   ```

3. **Dynamic routing via dispatcher:** The CTO agent (in any session) uses `ProjectResolver.resolve_by_task_id()` to look up the correct `agentId` string, then passes it to `session_spawn(agentId=<resolved_id>)`. No binding needed — just the agent identity must exist in OpenClaw config.

---

## Migration Path

### Phase 1: Catalog + Resolver (no config changes)
- Create `~/.openclaw/ds_eo/projects.yaml` with framework project definition
- Implement `project_resolver.py` module in DS-EO framework
- Extend `TaskIntakeManager` to accept `project_id` parameter
- No OpenClaw agent config changes needed yet

### Phase 2: DAL Agent Registration
- Add cto-dal, implementer-dal, reviewer-dal, pm-dal to `openclaw.json`
- Create `/home/deepsim/deepsim-ai-lab/ds_eo_project.yaml`
- Resume TASK_DAL_002 G2 using cto → project_resolver → cto-dal handoff

### Phase 3: Per-Project Agents List + Auto-Routing
- Generate `agents_project_list.json` from `ds_eo_project.yaml`
- Add webchat channel bindings per project
- Auto-detect project from workspace path in dispatcher

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| OpenClaw agent ID proliferation (3 roles × N projects) | Acceptable — 12 identities for 3 projects is manageable; each is lightweight JSON entry |
| Session name collisions across projects | Different agent IDs = different session namespaces in OpenClaw. No collision risk. |
| Task ID prefix collision | `PROJECT_<date>_<seq>` pattern enforced by ProjectResolver. DAL, DS_EO, WS all independent sequences. |
| Config drift between framework agents_list.json and per-project manifests | ProjectResolver is the single source of truth; ds_eo_project.yaml generates agents_project_list.json on install/refresh |
| Supervisor instance per project memory overhead | Lightweight (heartbeat timer + in-memory state dict); negligible (<1MB) |

---

## Summary

**The cleanest architecture:**
1. Keep framework agents exactly as-is (no changes to `ds_eo_openclaw/` core)
2. Add a **Project Catalog** (`projects.yaml`) at `~/.openclaw/ds_eo/`
3. Each consumer project declares its identity via `ds_eo_project.yaml`
4. The dispatcher gains a thin **ProjectResolver** that maps task → project → agent_id + workspace
5. New OpenClaw agent identities are registered statically (`cto-dal`, etc.) per project
6. Session isolation is automatic (OpenClaw sessions are keyed by agent ID)
7. Task IDs, artifact paths, supervisor instances all partitioned by project

This adds **one new framework module** (`project_resolver.py`), **one catalog format** (`projects.yaml`), and **one per-project config file** (`ds_eo_project.yaml`) — minimal change with maximum extensibility.
