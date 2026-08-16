# CTO Plan — TASK_DS_EO_045: Execution Strategy Polish (Phase C)

**Created:** 2026-08-16 07:50 PDT  
**Status:** PLANNED (awaiting user approval for Gate G1)  
**Author:** CTO 🏗️  
**Predecessor:** TASK_DS_EO_043 Phase A + TASK_DS_EO_044 Phase B  

---

## 1. Context & Scope

Phase A (TASK_DS_EO_043) delivered the foundation: execution strategy package with concurrent mode, capability assessor, and selector.  
Phase B (TASK_DS_EO_044) delivered sequential + shared model strategies with engine hooks.

**Phase C (this task) polishes:** The core functionality is complete. What remains are user-facing integration points, logging infrastructure, config schema documentation, package README, and auto-detection startup behavior — all low-risk additions that close the remaining gaps in the Phase A plan's deliverables table (§12).

---

## 2. Phase C Deliverables Analysis

### ✅ Already Done (Delivered by Phase B)
| Item | Status | Location |
|------|--------|----------|
| Migration guide | ✅ Complete | `TASK_DS_EO_044/MIGRATION_GUIDE.md` (249 lines) |
| AUTO_SELECTION_LOG template | ✅ Exists | `TASK_DS_EO_043/AUTO_SELECTION_LOG.md` (template format) |
| OVERRIDE_LOG template | ✅ Exists | `TASK_DS_EO_043/OVERRIDE_LOG.md` (template format) |

### ⚠️ Gaps to Close

The following items from TASK_DS_EO_043's deliverables table (§12) are either incomplete or missing:

---

## 3. Deliverable 1: `/eo execution strategy` Skill Command

### Current State
- The `ExecutionStrategySelector.set_manual_override()` and `switch_strategy()` methods exist in code
- **No user-facing skill command** to invoke these — the existing `skills/eo/SKILL.md` only covers `/eo mode manual` / `/eo mode automatic` (workflow mode, not execution strategy)

### Implementation Plan
Add four new commands to `skills/eo/SKILL.md`:

| Command | Action | Side Effects |
|---------|--------|-------------|
| `/eo execution strategy auto` | Clear manual override, re-run capability assessment | Persists override file with source=auto |
| `/eo execution strategy concurrent` | Force concurrent mode | Persists override; logs info-level confirmation |
| `/eo execution strategy sequential` | Force sequential mode | Persists override; warns if on constrained hardware |
| `/eo execution strategy shared_model` | Force shared model mode | Persists override; confirms model alignment across agents |

### Design Notes
- The selector already persists overrides to `STRATEGY_OVERRIDE.json` — we just need the skill layer that wraps it
- On constrained hardware, `sequential` should warn: *"Sequential mode will add ~2–5s per phase transition. Use 'shared_model' if all roles share the same model."*
- On `shared_model`, check if agents have aligned model configs before confirming

### File-by-File Changes
**File:** `skills/eo/SKILL.md` (~30 lines added)
- Add new "## Execution Strategy Commands" section with four command blocks
- Each block follows existing format: description, response format, implementation notes
- Update package list at bottom to include `commands.py` if needed

---

## 4. Deliverable 2: Auto-Detection at Startup (Not Lazy)

### Current State
- `ExecutionStrategySelector` resolves strategy **lazily** on first `get_or_resolve()` call
- Capability assessment only runs when the first agent phase begins
- The plan says: *"Auto-detection runs at DS-EO startup, not lazily at first task"*

### Implementation Plan
Add eager initialization to `ExecutionStrategyManager.__init__()`:

```python
async def __init__(self, workspace_root=None):
    # ... existing init ...
    # Eagerly resolve strategy at startup
    name, impl, report = self.selector.get_or_resolve()
    logger.info(f"Strategy auto-detected at startup: {name} (source: {report.source})")
```

This ensures the first agent phase doesn't pay the detection cost AND logs the initial selection.

### File-by-File Changes
**File:** `dispatcher/execution_strategy/__init__.py` (~5 lines modified)
- In `ExecutionStrategyManager.__init__()`, call `self.selector.get_or_resolve()` after initialization
- Log the result at INFO level (not DEBUG) — this is user-visible startup behavior

---

## 5. Deliverable 3: status_report() for PM Dashboard

### Current State
`status_report()` exists in code but returns basic info. Needs to be exposed via a visible mechanism (e.g., `/eo execution strategy status` command).

### Implementation Plan
- The existing `status_report()` already returns a dict with strategy name, source, capability report, and lifecycle state
- We just need the skill command to display it formatted
- Add as part of the `/eo execution strategy` command set: `/eo execution strategy status`

### File-by-File Changes
**File:** `skills/eo/SKILL.md` (~15 lines added)
- `/eo execution strategy status` — reads current state, formats and displays it
- Output includes: active strategy, selection source (auto vs. override), capability confidence, and lifecycle state

---

## 6. Deliverable 4: Package README (`dispatcher/execution_strategy/README.md`)

### Current State
- **Missing** — deferred from G4 approval due to low risk
- `__init__.py` has a module-level docstring that covers the public API adequately
- Migration guide covers user-facing documentation

### Implementation Plan
Create `dispatcher/execution_strategy/README.md` (~80 lines):
- Overview of the three strategies
- Quick-start: "How to switch modes" (1-liner)
- Architecture diagram (text-based)
- Public API reference
- Link to migration guide for full adoption details

### File-by-File Changes
**File:** `dispatcher/execution_strategy/README.md` (~80 lines, NEW)

---

## 7. Deliverable 5: Config Schema Reference

### Current State
- No YAML config schema exists — only JSON examples in `config-templates/`
- Strategy selection uses a sidecar JSON file (`STRATEGY_OVERRIDE.json`) and env var (`DS_EO_EXECUTION_STRATEGY`)
- The plan's "Config schema reference" is more about documenting the existing mechanisms

### Implementation Plan
Add to the migration guide (already exists) a dedicated "Configuration Reference" section covering:
1. **Override file** (`STRATEGY_OVERRIDE.json`) — path, format
2. **Environment variable** (`DS_EO_EXECUTION_STRATEGY`)
3. **Skill command** (`/eo execution strategy <mode>`)

No new config files needed — the existing mechanisms are sufficient and documented in the migration guide.

### File-by-File Changes
**File:** `MIGRATION_GUIDE.md` (~20 lines updated)
- Current migration guide already has a "Configuration Reference" section ✓
- No changes needed — it covers all three mechanisms adequately

---

## 8. Deliverable 6: Performance Benchmark Data

### Current State
The plan lists *"Performance benchmark data collected and documented (TTFT, memory peaks, total phase transition time)"* as an acceptance criterion (§10.3).

### Assessment
- **Not blocking for Phase C.** Benchmarking is an empirical measurement activity that requires running the system in production environments. The code is ready for benchmarking — users can compare modes by setting overrides and measuring phase transition times.
- Documenting how to run benchmarks (not collecting them) belongs in the migration guide's FAQ section.

### Implementation Plan
Add a short "Benchmarking" subsection to the migration guide:
- How to measure phase transition time per mode
- Expected baselines: concurrent (~0s overhead), sequential (+2–5s per phase), shared_model (~0s for subsequent agents)
- Tools: Ollama's `/api/ps` for memory tracking, DS-EO logs for TTFT

### File-by-File Changes
**File:** `MIGRATION_GUIDE.md` (~15 lines added to FAQ)

---

## 9. Deliverable 7: Auto-Selection Log (Runtime Logging)

### Current State
Templates exist (`AUTO_SELECTION_LOG.md`, `OVERRIDE_LOG.md`) but the code doesn't write to them at runtime. The templates are in TASK_DS_EO_043's directory, which is from Phase A — they should be documented as part of the migration guide instead.

### Implementation Plan
- **Option A (simpler):** Don't implement file logging — rely on existing `logger.info()` calls in selector.py and `status_report()`. The log messages are sufficient for production debugging.
- **Option B (complete):** Implement structured logging to the template files. Adds ~50 lines of logging infrastructure.

**Recommendation:** Option A is sufficient. The templates were placeholders from Phase A planning; actual runtime logging via Python's logging module is standard practice and documented in the migration guide under "What to monitor."

### File-by-File Changes
**File:** `MIGRATION_GUIDE.md` (~10 lines added)
- Section: "Monitoring & Troubleshooting" — describes what log messages to watch for (auto-selection, override changes, lifecycle events)
- Points users to `dispatcher/execution_strategy/selector.py` source for the actual logging

---

## 10. Acceptance Criteria

### 10.1 Functional
- [ ] `/eo execution strategy <mode>` commands work correctly for all four modes
- [ ] Auto-detection runs at `ExecutionStrategyManager` init time (startup), not on first task
- [ ] `status_report()` is accessible via skill command and returns formatted output
- [ ] Package README exists and describes the three strategies

### 10.2 Documentation
- [ ] Migration guide covers all configuration mechanisms + monitoring guidance
- [ ] Configuration reference section documents override file, env var, and skill command

### 10.3 Quality
- [ ] No regressions in existing 53 tests
- [ ] Zero new files outside `skills/eo/SKILL.md`, `dispatcher/execution_strategy/README.md`

---

## 11. File-by-File Plan

| # | Component | New? | Lines | Location |
|---|-----------|------|-------|----------|
| 1 | Skill commands (4 + status) | Modifies | ~30 | `skills/eo/SKILL.md` |
| 2 | Startup auto-detection | Modifies | ~5 | `dispatcher/execution_strategy/__init__.py` |
| 3 | Package README | New | ~80 | `dispatcher/execution_strategy/README.md` |
| 4 | Migration guide updates | Modifies | ~25 | `TASK_DS_EO_044/MIGRATION_GUIDE.md` |

**Total:** ~140 lines of code/docs, zero new files beyond README.

---

## 12. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Startup detection adds seconds to DS-EO init time | Low (~0.5s worst case) | Non-blocking: detect in background if needed; current eager approach is fine for local dev |
| Skill command conflicts with existing `/eo mode` commands | None — distinct command prefix (`execution strategy` vs `mode`) | Documented as separate command family |
| Package README adds no functional value, just docs | Low — it's documentation, not code | Minimal change scope; easy to revert if needed |

---

## 13. Timeline Estimate

| Task | Est. Hours |
|------|-----------|
| Skill commands (4 + status) | 2–3 |
| Startup auto-detection | 0.5 |
| Package README | 1–2 |
| Migration guide updates | 0.5–1 |
| Review + testing | 1–2 |
| **Total** | **5–8 hours** |

---

## 14. Gate Status

| Gate | Prerequisite Met? | Notes |
|------|------------------|-------|
| G1 (Plan Review) | Awaiting user approval | Low-risk polish on existing foundation |
| G2 (Implementation) | Pending G1 approval | — |
| G3 (Review) | Pending G2 completion | — |
| G4 (CTO Approval) | Pending G3 approval | — |
| G5 (PM Closure) | Pending G4 approval | — |

---

**End of CTO Plan for TASK_DS_EO_045.**  
Awaiting user approval to proceed.
