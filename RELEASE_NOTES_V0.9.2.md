# Release Notes — v0.9.2

**Release type:** feature + infrastructure improvement  
**Previous version:** 0.9.1  
**New version:** 0.9.2  
**Released by:** DS-EO engineering organization (manual release, 2026-08-16)  

---

## Executive Summary

v0.9.2 completes the **Execution Strategy Manager** across all three phases (A, B, C), delivering runtime control over how LLM models are loaded and released during DS-EO agent phases. This is a critical infrastructure improvement for users on constrained hardware (CPU-only, < 96GB RAM).

Additionally, this release includes comprehensive documentation updates covering all user-facing documents — README, ROADMAP, UPGRADING, TROUBLESHOOTING, and migration guides.

---

## What's New

### Execution Strategy Manager — Complete (Phases A + B + C)

The Execution Strategy Manager controls model loading behavior across the G1–G4 gate cycle. Users can now choose a strategy that matches their hardware:

| Mode | Loading Behavior | Best For | Phase Overhead |
|------|-----------------|----------|---------------|
| `auto` (default) | Intelligent detection picks best mode | Any system — let the assessor decide | N/A |
| `concurrent` | All agent models loaded simultaneously | 96GB+ RAM or discrete GPU | ~0s |
| `sequential` | One model at a time (load→use→unload) | Constrained hardware (< 96GB, CPU-only) | +2–5s per phase |
| `shared_model` | Single shared model instance across all agents | Same model for all roles | ~0s after first agent |

**User commands:**
```bash
/eo execution strategy status      # Check current mode
/eo execution strategy sequential  # Switch to sequential (persistent)
/eo execution strategy auto        # Back to intelligent defaults
```

### Infrastructure Improvements

- **Config timeout expansion:** Run timeout increased from 600s → 1800s across `agents.defaults`, `ollama provider`, and `compaction` — prevents session timeouts during long multi-tool turns on CPU-only inference.
- **Architecture documentation updated:** All user-facing documents now reflect Phase A/B/C completion, with adoption paths, migration guidance, and troubleshooting sections.

### Documentation Updates

| Document | Change |
|----------|--------|
| `PROJECT_STATUS.md` | Phase label updated to "COMPLETE — Phases A, B, C all closed" |
| `README.md` | Roadmap expanded with full Phase A/B/C details |
| `ROADMAP.md` | New v0.8+ Execution Strategy Manager section with strategy comparison and usage |
| `UPGRADING.md` | v0.9.2/v0.9.1 version history entries + upgrade guide for execution strategy |
| `docs/TROUBLESHOOTING.md` | New "Execution Strategy Troubleshooting" section + quick reference row |
| `dispatcher/execution_strategy/README.md` | Phase C section, architecture diagram updates |
| `ds_eo_execution_strategy_example.yaml` | Hardware note corrected to current (5 models / ~97GB) |

---

## Task Completion Summary

### TASK_DS_EO_043 — Execution Strategy Manager: Phase A ✅ CLOSED (G4 Approved 2026-08-14)
Foundation layer: `ConcurrentStrategy`, `CapabilityAssessor`, `ExecutionStrategySelector`, engine hooks (`prepare_phase`/`release_phase`), startup eager auto-detection.

### TASK_DS_EO_044 — Execution Strategy Manager: Phase B ✅ CLOSED (G4 Approved 2026-08-16)
Two new strategy implementations: `SequentialStrategy` (model lifecycle manager for constrained hardware) and `SharedModelStrategy` (ref-counted single-model sharing). 23 new tests.

### TASK_DS_EO_045 — Execution Strategy Manager: Phase C ✅ CLOSED (G4 Approved 2026-08-16)
User-facing `/eo execution strategy` skill commands, status reporting, migration guide, benchmarking guidance. Zero test regressions across 53 total tests.

---

## Hardware Recommendation

For your Tegra host (61GB unified memory, CPU-only inference):

- **Recommended:** `sequential` mode — one model at a time eliminates OOM/swapping risk
- **Alternative:** `shared_model` if all agents use the same model (qwen3.6:35b recommended)
- **Not recommended:** `concurrent` — 5 agent models total ~97GB exceeds available memory

To apply:
```bash
/eo execution strategy sequential
```

---

## Known Issues

### CPU Inference Speed
CPU-only inference at ~6-7 tok/s is a fundamental hardware constraint. Multi-tool turns on 35B models take 5-10+ minutes. The timeout expansion to 1800s provides headroom but does not eliminate the latency.

**Mitigation:** Keep idle model count low, use sequential mode, and ensure `OLLAMA_KEEP_ALIVE=300` in your Ollama service override to free memory for active model KV cache.

### CTO Role Boundary
The CTO can bypass its `write/edit/apply_patch` deny via `exec` + heredocs. Prompt rules exist but CPU inference pressure degrades adherence over long sessions. Recommend monitoring CTO output and reminding it of role boundaries if needed.

---

## Full Test Suite

- **53 tests** across Phases A+B (all passing)
- Phase C added skill commands with zero new test requirements
- No regressions from any previous release

---

*Release prepared by DS-EO engineering organization.*  
*Infrastructure fixes documented at `TASK_DS_EO_046/INFRASTRUCTURE_FIX_DIAGNOSIS.md`.*
