# DS-EO Roadmap

**DeepSim Engineering Organization — Evolution Plan**

---

## v0.1 — Self-Hosting Complete ✅

### What Was Delivered

| Component | Status | Details |
|-----------|--------|---------|
| Package Structure | ✅ | agents/, protocols/, templates/, scripts/, tests/ (42 files) |
| Agent Definitions | ✅ | CTO, Implementer, Reviewer with portable prompts and model placeholders |
| Engineering Protocols | ✅ | 6 core protocols: approval, communication, completion, delegation, handoff, review |
| Installation | ✅ | 7-step pipeline with backup/rollback; 54 tests passing |
| Task Governance | ✅ | Full CTO → Implementer → Reviewer → CTO approval chain documented |
| Canonical Repository | ✅ | `ds-eo-openclaw/` established as long-term home |
| Self-Hosting (Phase 2) | ✅ | Agents operate within canonical repo; first real task cycle executed (TASK_DS_EO_003) |

### Self-Hosting Validation Results

- First end-to-end task cycle completed inside `ds-eo-openclaw/` — TASK_DS_EO_003 (Roadmap creation)
- All four gates (G1–G4) functioned correctly with agents operating in the canonical workspace
- AGENTS.md established as workspace-level governance file
- Protocol symlinks from `docs/development/protocols/` to package source verified

---

## v0.2 — Ecosystem Planning 🏗️

### Objectives

1. **Cross-host deployment testing** — Install DS-EO on a clean OpenClaw host; validate full installation flow
2. **Task volume validation** — Execute 3–5 real tasks using DS-EO to confirm the workflow scales
3. **Protocol refinement** — Identify any gaps or ambiguities in the core protocols from production use
4. **Multi-platform analysis** — Document what would be required for each edition:
   - Claude Edition: prompt format differences, tool access model, installation mechanism
   - Codex Edition: agent config schema, protocol compatibility, deployment strategy
   - Gemini Edition: API integration patterns, agent definition format, workspace conventions

### Success Criteria

- [ ] DS-EO successfully installed on ≥2 clean OpenClaw hosts
- [ ] ≥3 real tasks completed using DS-EO without manual intervention beyond initial delegation
- [ ] Protocol gap analysis document produced with recommendations
- [ ] Multi-platform compatibility matrix documented (see docs/COMPATIBILITY.md for current host-specific data)

---

---

## v0.3 — Dispatcher Session Bridge Infrastructure 🔧 (Completed)

### What Was Delivered

| Component | Status | Details |
|-----------|--------|---------|
| TASK_DS_EO_026 | ✅ Closed | Fix Dispatcher `spawn_agent()` — real OpenClaw session creation + reliability verification |
| spawn_agent() bridge | ✅ Implemented | Bridge module that creates real sessions, not mock stubs |
| Session verification | ✅ Implemented | Automatic check that spawned sessions exist and are running in OpenClaw's session store |
| Reliability assertion | ✅ Implemented | Dispatcher never returns success without verified session existence |
| TASK_DAL_002 unblocked | ⏳ Pending | Awaiting host-side verification that the fix works on this instance |

### Key Finding

TASK_DAL_002 discovered a critical DS-EO infra defect: the Dispatcher's `spawn_agent()` path returned mock success without creating real sessions. This was the single largest reliability gap in the automatic mode workflow. The fix (TASK_DS_EO_026) establishes both session creation AND automatic verification as non-negotiable — future dispatcher operations must verify before claiming success.

### Reliability Impact for Future Tasks

This finding feeds into the **Workflow Supervisor/Watchdog** capability:
- The system must distinguish "real agent session running" from "dispatcher returned a mock success"
- Every spawn operation should automatically verify the returned session key
- Phantom sessions should be caught at the dispatcher level, not discovered later


### Tasks in v0.3
| Task | Title | Status | 
|------|-------|--------|
| TASK_DS_EO_026 | Fix Dispatcher spawn_agent() Real OpenClaw Session Creation | ✅ Closed | 
| **TASK_DS_EO_027** | **Workflow Supervisor / Watchdog** | **📋 Planning (G1 Awaiting)** |


---

## v1.0 — Platform Abstraction Layer 🌐

### Vision

Extract platform-independent concepts into a shared `ds-eo-core/` layer with adapter patterns for each platform:

```
ds-eo-core/                    ← Platform-independent roles, protocols, templates
    │
├── adapters/                  ← Platform-specific implementations  
│   ├── openclaw/              ← Current edition (this package)
│   ├── claude/                ← Future
│   ├── codex/                 ← Future
│   └── gemini/                ← Future
```

### Core abstractions to extract

| Concept | ds-eo-core representation | Platform adaptation |
|---------|--------------------------|-------------------|
| Role definition | `roles/<id>.md` — identity, responsibilities, tool policy model placeholders | Config format (JSON/YAML/TOML), tool access syntax, prompt loading mechanism |
| Protocol rules | `protocols/*.md` — core governance rules | Platform-specific gate mechanisms (approval workflows vary by platform) |
| Task lifecycle | `TASK_<id>/` with 4 standard artifacts | Directory creation mechanism, session management, handoff delivery |
| Template formats | `templates/*.md` — document structures | Platform rendering/processing differences |

### Success Criteria

- [ ] All protocol rules are platform-independent (no OpenClaw-specific concepts in core)
- [ ] ds-eo-core passes the same 54 verification tests used by the OpenClaw edition
- [ ] OpenClaw Edition v0.2 exists as an adapter layer on top of ds-eo-core
- [ ] At least one additional platform edition prototype (Claude or Codex)

---

## Future Editions (Post-v1.0)

### DS-EO Claude Edition

**Primary differences to address:**
- Prompt loading mechanism (Anthropic's system prompt vs OpenClaw's workspace context injection)
- Tool access model (Constrained function calling vs OpenClaw's tool groups)
- Agent registration (Claude Code's agent config format)

### DS-EO Codex Edition

**Primary differences to address:**
- Agent definition schema (OpenAI codex CLI format)
- Session management and handoff delivery
- Protocol enforcement mechanisms

### DS-EO Gemini Edition

**Primary differences to address:**
- Google AI Studio integration patterns
- Workspace/context injection model
- Plugin/extension ecosystem compatibility

---

## Long-Term Vision

```
                    ┌─────────────┐
                    │  ds-eo-core  │ ← Platform-independent engineering concepts
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
     DS-EO OpenClaw   DS-EO Claude    DS-EO Codex
      Edition          Edition         Edition
           │               │               │
           └───────────────┼───────────────┘
                           ▼
                  Engineering Teams
                           │
                           ▼
                    Software Projects
                           │
                      ┌────┴────┐
                      ▼         ▼
                   DS-AIOS    Other Projects
```

**Guiding principle**: Every platform edition must deliver the same engineering experience — disciplined, review-gated, artifact-based handoffs — regardless of the underlying agent platform's mechanics.

---

*Roadmap maintained by CTO (ollama/qwen3.6:35b)*  
*Last updated: 2026-07-28*
