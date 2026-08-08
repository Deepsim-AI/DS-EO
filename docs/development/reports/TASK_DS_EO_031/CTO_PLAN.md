---
produced_by: cto
role: CTO
task_id: TASK_DS_EO_031
gate: G1 (plan approved)
created_at: 2026-08-07T17:40:00Z
---

# CTO Plan — TASK_DS_EO_031

## Technical Analysis

### Problem Statement

PM and CTO were both bound to `ollama/qwen3.6:35b`. The role-boundary problem observed in TASK_DS_EO_030 demonstrated that a PM using the same model as CTO can easily drift into CTO-level analysis (architecture review, gap analysis, planning artifacts). Assigning a lighter model to PM provides both a practical specialization and a mechanical role boundary.

### Model Availability

- `gpt-oss:20b` — installed locally, verified working via `ollama run gpt-oss:20b`
- `qwen3.6:35b` — confirmed operational (this session)
- `ornith:35b` — confirmed installed
- `laguna-xs-2.1:q4_K_M` — confirmed installed

### Configuration Files That Bind Models

| File | What It Contains | Must Update? |
|------|-----------------|-------------|
| `~/.openclaw/openclaw.json` (agents.list) | Live agent-to-model bindings used by OpenClaw runtime | **YES** |
| `ds_eo_manifest.yaml` | Package manifest with default model suggestions | **YES** |
| `agents_list.json` | Package-level agents list (source of truth for package) | **YES** |
| `agents/pm.md` | PM role prompt with model placeholder suggestion | **YES** |
| `agents/cto.md` | CTO role prompt — no change needed | No |
| `AGENTS.md` | Engineering org document listing all agent models | **YES** |

### Detailed Changes

#### 1. OpenClaw Runtime (`~/.openclaw/openclaw.json`)

Change the PM agent entry:
```json
{
  "id": "pm",
  "model": "ollama/gpt-oss:20b",   // was "ollama/qwen3.6:35b"
  ...
}
```

**Note**: The key is `ollama/gpt-oss:20b` (with `ollama/` prefix for the provider). OpenClaw uses this convention to resolve against local Ollama models.

#### 2. Package Manifest (`ds_eo_manifest.yaml`)

Change the PM default_model from `"ollama/qwen3.6:35b"` to `"ollama/gpt-oss:20b"`.

Update the comment line that says "Same model family as CTO; identity is in persona, not model" to reflect the new specialization rationale.

#### 3. Package Agents List (`agents_list.json`)

Change PM entry's `"model"` from `"ollama/qwen3.6:35b"` to `"ollama/gpt-oss:20b"`.

#### 4. PM Role Prompt (`agents/pm.md`)

Update the model placeholder section and add a rationale paragraph explaining:
- PM now uses `gpt-oss:20b` (lighter, specialized for coordination)
- Rationale: separates coordination work from technical analysis; reinforces mechanical boundary since different models = different session isolation

#### 5. AGENTS.md

Update the CTO role definition section to reflect that PM and CTO now use different models (it previously stated they share the same model). Remove or update any comment suggesting they share a model family.

### Rollback Procedure

1. **OpenClaw runtime**: Revert `~/.openclaw/openclaw.json` PM model entry back to `"ollama/qwen3.6:35b"` and restart gateway (`openclaw gateway restart`)
2. **Package files**: Reverse all changes in `ds_eo_manifest.yaml`, `agents_list.json`, `agents/pm.md`, and `AGENTS.md` — revert to pre-change git state via `git checkout`

### Validation Steps

1. `openclaw agents list` → confirm PM shows `ollama/gpt-oss:20b`, all others unchanged
2. `openclaw gateway restart` → no startup errors
3. `python -m pytest tests/ --tb=no 2>&1 | tail -5` → all pass (no config-test regressions expected)

## Acceptance Criteria Mapping

| Req | Status | Details |
|-----|--------|---------|
| Req 1: PM → gpt-oss:20b | **Approved** | 5 files to update |
| Req 2: CTO → qwen3.6:35b | Confirmed no change needed | Already bound correctly |
| Req 3: Implementer → ornith:35b | Confirmed no change needed | Already bound correctly |
| Req 4: Reviewer unchanged | Confirmed no change needed | Already correct |
| Req 5: Config consistency | **Approved** | All 6 locations updated |
| Req 6: Role-boundary docs | **Approved** | PM prompt + AGENTS.md update |
| Req 7: Validation | **Approved** | Agents list + test suite + restart |

## Risk Assessment

- **Low**: gpt-oss:20b is already installed and verified. No new dependencies.
- **Low**: Change is purely configuration — all files have git history for rollback.
- **Medium**: If gpt-oss:20b has capability gaps for PM workload, may need to adjust the PM's role prompt to not rely on complex reasoning from the lighter model.

## Implementation Steps

1. Update `~/.openclaw/openclaw.json` — PM model binding (critical path)
2. Restart OpenClaw gateway to apply config change
3. Verify with `openclaw agents list`
4. Update `ds_eo_manifest.yaml` (package manifest)
5. Update `agents_list.json` (package-level source of truth)
6. Update `agents/pm.md` (role prompt rationale)
7. Update `AGENTS.md` (engineering org documentation)
8. Run test suite to confirm no regressions
