# CTO_APPROVAL.md — TASK_DS_EO_DSH_005

**TASK_ID:** `TASK_DS_EO_DSH_005`  
**Title:** Phase 2: Model Registry Swap (D1)  
**CTO:** qwen3.6:35b  
**Date:** 2026-09-29  

## Gate G4 — Approval Status: ✅ APPROVED

### Implementation Verification Against CTO Plan

#### M1: model_registry.py (NEW FILE) ✅
- Created at `ds_eo_openclaw/adapter/model_registry.py` (181 lines)
- Provides `get_registry()` singleton, `ModelRegistry` class with manifest-backed defaults
- `resolve(model_uri, runtime)` maps between runtime-specific URIs (ollama → dsh://model/…)
- Graceful fallback to hardcoded defaults when manifest unavailable
- Backward compat: `_LEGACY_DEFAULT_MODEL_MAP` and `legacy_default_model()` kept

#### M2: session_spawn.py changes ✅
- Line 23: Added import `from ..adapter.model_registry import get_registry, legacy_default_model`
- Lines 48-52: Renamed `DEFAULT_MODEL_MAP` → `_LEGACY_DEFAULT_MODEL_MAP` (backward compat)
- Line 76: Kept legacy map initialization for backward-compat code paths only
- Lines 110-115: Replaced direct lookup with registry call:
  ```python
  registry = get_registry()
  target_model = (model_override or
                 registry.default_model_for_role(agent_role) or
                 legacy_default_model(agent_role))
  ```

#### M3: workflow_defs/default.yaml placeholders ✅
- Line 9: `ollama/qwen3.6:35b` → `<MODEL_CTO>`
- Line 19: `ollama/qwen3.8:27b` → `<MODEL_IMPLEMENTER>`
- Line 28: `ollama/laguna-xs-2.1:q4_K_M` → `<MODEL_REVIEWER>`
- Line 38: `ollama/ornith:35b` → `<MODEL_PM>`

#### M4: capability_assessor.py generic provider prefix ✅
- Line ~202: Replaced `model.replace("ollama/", "")` with generic:
  ```python
  short_name = re.sub(r"^([a-z][a-z0-9]*)/", "", model)
  ```
- Added `import re` at top of file

### Residual Hardcoded ollama References

Only in `_LEGACY_DEFAULT_MODEL_MAP` (backward compat alias) and in docstrings. No active code path uses them directly — all consumers now go through `get_registry()` or its legacy fallback.

### Backward Compatibility

- `_LEGACY_DEFAULT_MODEL_MAP` kept as direct dict for any code that bypasses the registry
- `legacy_default_model(role)` provides same fallback behavior as before
- Manifest-driven defaults take priority; hardcoded values are only fallbacks

## Conclusion

Phase 2 implementation matches the CTO_PLAN.md exactly. Model resolution is now runtime-agnostic via `ModelRegistry`. All source model URIs replaced with placeholders in config, and all code paths use registry lookups instead of hardcoded ollama references.

**G4: APPROVED** — Ready for PM G5 closure (commit to dsh-migration branch, update PROJECT_STATUS.md).
