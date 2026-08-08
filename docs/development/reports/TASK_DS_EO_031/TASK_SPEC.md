---
produced_by: pm
role: PM
task_id: TASK_DS_EO_031
gate: G0 (intake)
created_at: 2026-08-07T17:15:00Z
---

# Task Spec — TASK_DS_EO_031

## Objective

Specialize PM and CTO roles by assigning different LLM models, reserving the stronger Qwen 35B model for CTO-level technical analysis while using a lighter model for the PM's coordination/intake work.

## Requirements

### Req 1: PM Model Change
- Bind PM agent to `gpt-oss:20b` (already installed locally via Ollama)
- Verify the change takes effect in OpenClaw's active configuration
- Verify all existing model assignments remain unchanged unless specified

### Req 2: CTO Model Verification
- Confirm CTO remains bound to `ollama/qwen3.6:35b` (no change)

### Req 3: Implementer Model Verification
- Confirm Implementer remains bound to `ollama/ornith:35b` (no change)

### Req 4: Reviewer Model Verification
- Confirm Reviewer remains bound to `ollama/laguna-xs-2.1:q4_K_M` (no change unless required)

### Req 5: Configuration Update Scope
- Update all configuration files that bind agents to models consistently:
  - OpenClaw agent registry (`~/.openclaw/openclaw.json` — `agents.list[]` entries)
  - DS-EO manifest (`ds_eo_manifest.yaml`)
  - Agents list file (`agents_list.json`)
  - Role prompt files (`agents/pm.md`, `agents/cto.md`)
  - AGENTS.md engineering org document
- No other configuration should be modified

### Req 6: Role-Boundary Documentation
- Update PM role prompt to clarify that PM is now using a lighter model and should focus strictly on intake/coordination/handoff
- Document the rationale for model specialization in relevant protocols

### Req 7: Validation
- Verify all agents list correctly after configuration update via `openclaw agents list`
- Confirm no startup errors or warnings from OpenClaw
- Run test suite to verify no regressions

## Acceptance Criteria

1. **PM agent uses `gpt-oss:20b`** — confirmed via `openclaw agents list` showing correct model binding
2. **CTO agent still uses `qwen3.6:35b`** — confirmed via `openclaw agents list`
3. **Implementer agent still uses `ornith:35b`** (or equivalent working implementation model) — confirmed
4. **Reviewer agent model unchanged** — confirmed via `openclaw agents list`
5. **All config files updated consistently** — no stale references to old PM model in any documented location
6. **PM role prompt updated** — reflects new lighter-model specialization rationale
7. **Tests pass** — no regressions from configuration changes

## Constraints

- Minimal, reversible change only
- No architectural redesign of DS-EO
- No workflow behavior changes beyond model binding
- Document rollback procedure explicitly

