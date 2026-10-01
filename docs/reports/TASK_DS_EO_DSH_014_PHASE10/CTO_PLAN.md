TASK_DS_EO_DSH_014 — Phase 10: DSH Headless Adapter + Baseline Repair

---
produced_by: CTO (qwen3.8:27b, CTO this pass)
session_id: jetson-dsh-workspace (ornith 1.5:35b pass)
role: CTO
task_id: TASK_DS_EO_DSH_014
gate: G1
---

## 1. Summary

Two parts:

A. Governance closure of Phase 10 — fold the Phase 10 work product (the untracked dsh_headless_adapter.py, adapter tests, smoke test, architecture doc, and completion report) into the canonical task directory, and fold the off-convention TASK_DS_EO_050 directory in.
B. Baseline repair — about 15 failing tests are rooted in (1) the 033 rename, (2) the runtime_api.py DSH factory requiring a base URL, and (3) stale ds-eo_openclaw paths in the manifest and in test_phase0.py. Wire the DshHeadlessAdapter into the build/test path, repair the tests, and clean the 033 references.

## 2. Gate Sequence

1. G1 — User approval of THIS plan (current gate).
2. G2 — Implementer applies changes in canonical dir per this plan; CTO confirms.
3. G3 — Reviewer produces REVIEW_REPORT.md with a score matrix; CTO accepts as input to G4.
4. G4 — CTO final approve/reject.

## 3. Work Items

### WI-1: Fold TASK_DS_EO_050 into canonical directory

Move, not copy:
- docs/reports/TASK_DS_EO_050/ -> docs/reports/TASK_DS_EO_DSH_014_PHASE10/
- Delete the now-empty docs/reports/TASK_DS_EO_050/
- The directory must contain: CTO_PLAN.md (this), REVIEW_REPORT.md (reviewer), DSH_HEADLESS_ADAPTER_ARCHITECTURE.md, PHASE10_COMPLETION_REPORT.md, TASK_DS_EO_051_COMPLETION_REPORT.md (if Phase 11 produced).
- Do not add file types beyond canonical Phase 10 deliverables. Any extra must be surfaced to the user.

### WI-2: Fix stale ds-eo_openclaw references

- ds_eo_manifest.yaml line 117: package.directory ds_eo_openclaw -> ds_eo_dsh
- tests/adapter/test_phase0.py: phase-0 openclaw adapter imports (from ..adapter.openclaw_adapter import ...) corrected to the renamed bridge module path (from ..adapter.openclaw_bridge import ...).

### WI-3: Repair the runtime_api.py factory

DSH adapter is now production-ready; the factory raises when no DSH HTTP endpoint is configured, breaking ~15 phase-0 tests. New resolution:
- runtime dsh/auto/default with NO DSH HTTP endpoint configured -> DshHeadlessAdapter.
- runtime dsh/auto/default WITH a configured DSH HTTP endpoint -> still HTTP DshRuntimeAdapter (preserve intent; keep the explicit-endpoint path).
- runtime openclaw -> OpenClawRuntimeAdapter (unchanged).
- runtime http -> HttpRuntimeAdapter if present.
- Update the docstring at runtime_api.py:195 to reflect this.

### WI-4: Repair remaining test imports affected by the 033 rename

- discoverer / spawn_manager now import from the ds_eo_dsh package. Fix any remaining imports of the old package layout (session_health, dispatcher) to the canonical ds_eo_dsh paths.
- Re-scan the repo for any stale ds-eo_openclaw absolute import paths.

### WI-5: Baseline full suite

After WI-1..WI-4 run the full suite. Target: 0 failures with a documented set of legitimate skips (no fabrication). Confirm the skip list (e.g., openclaw-connection tests) is expected.

## 4. Definition of Done

- TESTS_PASS_STATUS.md written under TASK_DS_EO_DSH_014 with current results.
- Zero failing tests; skips legitimate and documented.
- 033 references resolved; no stale committed ds-eo_openclaw import strings. Any remaining (intentional) documentation mentions listed in the closing note.
- CTO_PLAN/Gates G1..G4 recorded; REVIEW_REPORT.md present.

## 5. Risks

- Widening the factory default to DshHeadlessAdapter is safe: the HTTP adapter only existed when a DSH HTTP endpoint was configured, and none is.
- A project-wide import scan is recommended to catch any other pre-033 rename import paths.

## 6. Scope Boundaries

- No new features beyond wiring the headless adapter + repair.
- No re-architecture of runtime_api.py beyond resolution at line 195.
- Do not modify openclaw_bridge.py behavior (only its module path).
