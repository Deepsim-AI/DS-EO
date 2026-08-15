# TASK_DS_EO_041 — Phase 2 Implementation Plan (G2)

**Status:** WIP  
**Date:** 2026-08-13  

---

## Objective

Register DAL agent identities (`cto-dal`, `implementer-dal`, `reviewer-dal`, `pm-dal`) in the DS-EO framework's `agents_list.json` and create the per-project identity manifest for `/home/deepsim/deepsim-ai-lab`. This is **Phase 2** — no workflow engine changes, no dispatcher routing modifications yet. Just registration + config scaffolding.

## Constraints (from user)

1. **Do NOT register DAL agents in OpenClaw `openclaw.json`** — that's Phase 3
2. **Existing DS-EO agents must not be affected** — framework agents (cto, implementer, reviewer, pm) stay exactly as-is in the file
3. **TASK_DAL_002 must safely resolve to DAL workspace** via `ProjectResolver`

## What Gets Modified

### 1. `/home/deepsim/ds_eo_openclaw/agents_list.json` — ADDITIONS ONLY

Add four new agent entries for DAL, mirroring the framework agents' exact tool configurations:

| New Agent ID | Framework Role | Workspace | Tools (mirrored from framework) |
|---|---|---|---|
| `cto-dal` | cto | `/home/deepsim/deepsim-ai-lab` | Same allow/deny as framework `cto` |
| `implementer-dal` | implementer | `/home/deepsim/deepsim-ai-lab` | Same allow/deny as framework `implementer` |
| `reviewer-dal` | reviewer | `/home/deepsim/deepsim-ai-lab` | Same allow/deny as framework `reviewer` |
| `pm-dal` | pm | `/home/deepsim/deepsim-ai-lab` | Same allow/deny as framework `pm` |

The four new entries must be appended at the **end** of the existing 4-entry array. The original four entries (cto, implementer, reviewer, pm) are **not modified at all**.

### 2. `/home/deepsim/deepsim-ai-lab/ds_eo_project.yaml` — NEW FILE

Per-project identity manifest declaring how DAL agents map to the framework:

```yaml
project_id: "dal"
project_name: "Deepsim AI Lab Website"
framework_root: "/home/deepsim/ds_eo_openclaw"
task_id_prefix: "DAL"

agent_mappings:
  # cto-dal mirrors framework cto
  - framework_agent: "cto"
    project_agent: "cto-dal"
    model: "ollama/qwen3.6:35b"
    workspace: "/home/deepsim/deepsim-ai-lab"
    tools_allow: ["group:fs", "web_search", "web_fetch", "sessions_list", "session_status", "memory_search", "memory_get", "exec", "process", "sessions_spawn", "sessions_send"]
    tools_deny: ["write", "edit", "apply_patch"]

  # implementer-dal mirrors framework implementer
  - framework_agent: "implementer"
    project_agent: "implementer-dal"
    model: "ollama/ornith:35b"
    workspace: "/home/deepsim/deepsim-ai-lab"
    tools_allow: ["group:fs", "group:runtime", "group:web", "group:sessions", "group:memory"]
    tools_deny: []

  # reviewer-dal mirrors framework reviewer
  - framework_agent: "reviewer"
    project_agent: "reviewer-dal"
    model: "ollama/laguna-xs-2.1:q4_K_M"
    workspace: "/home/deepsim/deepsim-ai-lab"
    tools_allow: ["group:fs", "web_search", "web_fetch", "exec", "process", "sessions_list", "session_status", "memory_search", "memory_get"]
    tools_deny: ["write", "edit", "apply_patch"]

  # pm-dal mirrors framework pm
  - framework_agent: "pm"
    project_agent: "pm-dal"
    model: "ollama/gpt-oss:20b"
    workspace: "/home/deepsim/deepsim-ai-lab"
    tools_allow: ["group:fs", "web_search", "web_fetch", "exec", "write", "sessions_list", "session_status", "memory_search", "memory_get"]
    tools_deny: ["process", "edit", "apply_patch", "browser", "canvas", "nodes"]
```

### 3. `/home/deepsim/ds_eo_openclaw/dispatcher/project_resolver/resolver.py` — ENHANCEMENT

Add a new method `load_project_manifest(project_id)` that reads a project's `ds_eo_project.yaml` and validates it against the catalog. Also add `resolve_by_agent_id(agent_id)` to look up DAL agents directly by their full ID (e.g., `"cto-dal"` → AgentIdentity).

This enables the dispatcher to resolve both:
- By task prefix: `TASK_DAL_002` → project=`dal` → agent=`cto-dal`
- By agent ID directly: `cto-dal` → AgentIdentity with workspace+model

### 4. `/home/deepsim/deepsim-ai-lab/docs/dispatchers/` — CREATE DIRECTORY

Required for the next task to write its dispatcher state under the DAL project's directory.

## Verification Steps

1. `agents_list.json` has exactly 8 entries (4 original + 4 new), originals unchanged
2. ProjectResolver can resolve `"cto-dal"` via `resolve_by_agent_id()`
3. `resolve_by_task_id("TASK_DAL_002")` returns project=`dal` with agent `cto-dal`
4. No framework agent configuration altered (verified by checksum comparison)

## Files Changed Summary

| File | Action | Lines |
|------|--------|-------|
| `/home/deepsim/ds_eo_openclaw/agents_list.json` | **Modified** — append 4 entries | +80 lines |
| `/home/deepsim/deepsim-ai-lab/ds_eo_project.yaml` | **Created** | ~50 lines |
| `/home/deepsim/deepsim-ai-lab/docs/dispatchers/` | **Directory created** | — |
| `/home/deepsim/ds_eo_openclaw/dispatcher/project_resolver/resolver.py` | **Modified** — add `resolve_by_agent_id()` | ~30 lines |

## What Phase 2 Does NOT Do

- No changes to `openclaw.json` or gateway bindings (Phase 3)
- No modifications to WorkflowEngine, SessionSpawnManager, or TaskIntakeManager routing logic
- No new workflow transitions
- No DAL task directories created yet (TASK_DAL_001/002)
