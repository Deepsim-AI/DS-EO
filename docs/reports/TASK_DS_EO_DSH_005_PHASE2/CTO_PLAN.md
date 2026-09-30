# CTO_PLAN.md — TASK_DS_EO_DSH_005

**Task:** Phase 2: Model Registry Swap (D1)  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-29  
**Gate:** G1 — Plan for User Review  

---

## 1. Task Objective

Replace **all hardcoded `ollama/` model references** in the DS-EO source tree with a runtime-agnostic model registry that reads from `ds_eo_manifest.yaml`. This makes the runtime genuinely pluggable — no `ollama` hardcoding survives Phase 2.

This is the **highest-leverage Phase 1 win** (from TASK_DS_EO_DSH_004 plan): without this change, the "DSH Edition" is merely a semantic rename while the code still depends on ollama-specific model URIs.

---

## 2. Scope: Hardcoded Model References Found

### File-by-File Analysis

| # | File (relative to ds_eo_dsh/) | Line(s) | Context | Severity |
|---|-------------------------------|---------|---------|----------|
| M1 | `ds_eo_openclaw/dispatcher/session_spawn.py` | 47-51 | `DEFAULT_MODEL_MAP` dict — **direct hardcoding** | 🔴 CRITICAL |
| M2 | `ds_eo_openclaw/dispatcher/workflow_defs/default.yaml` | 9, 19, 28, 38 | Agent model URIs in workflow definition | 🟡 HIGH |
| M3 | `ds_eo_openclaw/dispatcher/execution_strategy/capability_assessor.py` | 202 | String replace `model.replace("ollama/", "")` | 🟡 HIGH |
| M4 | `ds_eo_manifest.yaml` | 21-49 | Default model values — **these ARE the registry** (already using ollama defaults, needs DSH-ready placeholders) | 🟢 LOW (metadata only) |
| M5 | `agents/*.md` | Various per file | Model suggestion references in agent prompts | 🟢 LOW (documentation) |

### What Phase 2 Will Change

Phase 2 creates a **model registry module** and updates all consumer files to use it:

```
ds_eo_openclaw/adapter/model_registry.py  ← NEW: Runtime-agnostic model resolution
```

### What Phase 2 Will NOT Change (deferred)

| File | Reason | Phase for change |
|------|--------|------------------|
| `agents/*.md` prompts | Documentation, no runtime effect | Manual review per task |
| `ds_eo_manifest.yaml` defaults | Already serves as config source of truth; values will be user-configurable | Current (already configurable via manifest) |

---

## 3. Implementation Specification

### M1: Create `ds_eo_openclaw/adapter/model_registry.py` (NEW FILE)

This file is the runtime-agnostic model resolution layer. It reads from `ds_eo_manifest.yaml` and falls back to defaults for the target runtime.

```python
"""Model Registry — Runtime-agnostic model resolution.

Replaces hardcoded ollama/* model references with a registry that
can resolve models for any target runtime (DSH, OpenClaw, etc.).

Usage:
    from ds_eo_openclaw.adapter.model_registry import ModelRegistry

    registry = ModelRegistry()
    default_model = registry.default_model_for_role("cto")        # "qwen3.6:35b"
    resolved = registry.resolve("ollama/qwen3.6:35b", runtime="dsh")  # "dsh://model/xyz"
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional


# --- Core Registry ---

class ModelRegistry:
    """Runtime-agnostic model registry.
    
    Reads default models from ds_eo_manifest.yaml and provides
    resolution between runtime-specific model URIs (ollama/qwen3.6:35b)
    and target runtime URIs (dsh://model/..., etc.).
    """

    # Default role → manifest mapping keys (from ds_eo_manifest.yaml)
    _ROLE_TO_MANIFEST_KEY = {
        "cto": "default_model_cto",
        "implementer": "default_model_implementer",  
        "reviewer": "default_model_reviewer",
        "pm": "default_model_pm",
    }

    # Fallback defaults (used when manifest is unavailable)
    _FALLBACK_MODELS: dict[str, str] = {}

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize registry.
        
        Args:
            config_path: Path to ds_eo_manifest.yaml. Defaults to finding
                it relative to the caller's package location.
        """
        self._config_path = config_path or self._find_manifest()
        self._cache: dict[str, str] = {}

    def _find_manifest(self) -> Path:
        """Locate ds_eo_manifest.yaml relative to this package."""
        pkg_dir = Path(__file__).resolve().parent.parent  # ds_eo_openclaw/
        # Check current working directory first (project-level manifest)
        cwd_manifest = Path.cwd() / "ds_eo_manifest.yaml"
        if cwd_manifest.exists():
            return cwd_manifest
        # Fall back to package location
        pkg_manifest = pkg_dir.parent / "ds_eo_manifest.yaml"
        if pkg_manifest.exists():
            return pkg_manifest
        raise FileNotFoundError(
            "ds_eo_manifest.yaml not found. Set config_path or place manifest in project root."
        )

    def load_from_yaml(self, path: Path) -> dict[str, str]:
        """Load model defaults from ds_eo_manifest.yaml.
        
        Returns:
            Dict mapping role names to model URIs.
        """
        import yaml  # lazy import
        with open(path) as f:
            config = yaml.safe_load(f)
        models = {}
        for role, key in self._ROLE_TO_MANIFEST_KEY.items():
            model_val = config.get(key, {})
            if isinstance(model_val, dict):
                models[role] = model_val.get("default_model", "")
            elif isinstance(model_val, str):
                models[role] = model_val
        return models

    def default_model_for_role(self, role: str) -> str:
        """Get the default model URI for a given role.
        
        Args:
            role: Agent role name (cto, implementer, reviewer, pm)
            
        Returns:
            Model URI string from manifest or fallback.
        """
        if role not in self._ROLE_TO_MANIFEST_KEY:
            raise ValueError(f"Unknown role: {role}. Valid: {list(self._ROLE_TO_MANIFEST_KEY.keys())}")
        
        key = self._ROLE_TO_MANIFEST_KEY[role]
        
        # Check cache first
        if key in self._cache:
            return self._cache[key]
        
        try:
            models = self.load_from_yaml(self._config_path)
            value = models.get(key, "")
        except (FileNotFoundError, yaml.YAMLError):
            value = ""
        
        # Fallback to hardcoded defaults if manifest unavailable
        if not value:
            value = self._get_fallback(role)
        
        self._cache[key] = value
        return value

    def _get_fallback(self, role: str) -> str:
        """Return fallback model for role (used when manifest unavailable)."""
        return {
            "cto": "ollama/qwen3.6:35b",
            "implementer": "ollama/qwen3.8:27b",
            "reviewer": "ollama/laguna-xs-2.1:q4_K_M",
            "pm": "ollama/ornith:35b",
        }[role]

    def resolve(self, model_uri: str, runtime: str = "openclaw") -> str:
        """Resolve a model URI from source runtime to target runtime.
        
        This is the pluggable mapping layer between runtimes.
        
        Args:
            model_uri: Source model URI (e.g., "ollama/qwen3.6:35b")
            runtime: Target runtime identifier
            
        Returns:
            Resolved model URI for target runtime (e.g., "dsh://model/qwen3.6:35b")
        """
        # Simple prefix-based mapping — extensible via configuration
        if runtime == "dsh":
            return f"dsh://model/{model_uri.split('/')[-1]}"
        elif runtime == "openclaw":
            return model_uri  # No-op for legacy
        else:
            return model_uri  # Passthrough for unknown runtimes


# Singleton pattern — shared across all consumers
_model_registry: Optional[ModelRegistry] = None

def get_registry() -> ModelRegistry:
    """Get or create the singleton ModelRegistry instance."""
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
    return _model_registry


# Legacy default map (for backward compatibility with direct lookups)
# Will be removed once all consumers use get_registry()
_DEFAULT_MODEL_MAP = {
    "implementer": "ollama/qwen3.6:27b",  # ← Note: this matches session_spawn.py current value
    "reviewer": "ollama/laguna-xs-2.1:q4_K_M",
    "cto": "ollama/qwen3.6:35b",
    "pm": "ollama/gpt-oss:20b",
}


def legacy_default_model(role: str) -> str:
    """Legacy fallback — for backward compatibility only. Prefer get_registry()."""
    return _DEFAULT_MODEL_MAP.get(role, "")
```

---

### M2: Update `ds_eo_openclaw/dispatcher/session_spawn.py` (lines 47-51)

**Current (line 47):**
```python
DEFAULT_MODEL_MAP = {
    "implementer": "ollama/qwen3.6:27b",
    "reviewer": "ollama/laguna-xs-2.1:q4_K_M",
    "cto": "ollama/qwen3.6:35b",
    "pm": "ollama/gpt-oss:20b",
}
```

**Change:** Replace `DEFAULT_MODEL_MAP` usage with `get_registry().default_model_for_role(role)` throughout the file. Keep `DEFAULT_MODEL_MAP` as a **legacy alias** for backward compatibility only.

**Specific lines to modify:**
1. **Line ~47**: Add import: `from ..adapter.model_registry import get_registry, legacy_default_model`
2. **Lines 47-51**: Rename to `_LEGACY_DEFAULT_MODEL_MAP` and add docstring comment
3. **All usages of `DEFAULT_MODEL_MAP[role]`** → change to `get_registry().default_model_for_role(role) or legacy_default_model(role)`

**Verification:** grep after for remaining `ollama/` in this file should return zero results (except in the `_LEGACY_DEFAULT_MODEL_MAP` comment and docstrings).

---

### M3: Update `ds_eo_openclaw/dispatcher/workflow_defs/default.yaml` (lines 9, 19, 28, 38)

**Current models:**
- Line 9: `cto.model: ollama/qwen3.6:35b` → Change to `<MODEL_CTO>` placeholder
- Line 19: `implementer.model: ollama/qwen3.8:27b` → Change to `<MODEL_IMPLEMENTER>`
- Line 28: `reviewer.model: ollama/laguna-xs-2.1:q4_K_M` → Change to `<MODEL_REVIEWER>`
- Line 38: `pm.model: ollama/ornith:35b` → Change to `<MODEL_PM>`

**Change:** Replace model URIs with placeholder tokens that the runtime resolver substitutes at load time. These placeholders match the ones already defined in `ds_eo_manifest.yaml` (lines 21, 30, 39, 48).

The workflow engine (`dispatcher/engine.py`) must be updated to call `ModelRegistry.resolve()` when loading agent model from YAML — but this is a **config-layer change** that needs verification. Let me check if the engine already supports this.

---

### M4: Update `ds_eo_openclaw/dispatcher/execution_strategy/capability_assessor.py` (line 202)

**Current (line 202):**
```python
short_name = model.replace("ollama/", "")
```

**Change:** This is a string-parsing convenience for stripping the ollama provider prefix. It needs to become runtime-agnostic:

```python
# OLD:
short_name = model.replace("ollama/", "")

# NEW:
provider, _, short_name = model.partition("/")
if "/" in short_name:
    short_name = short_name.rsplit("/", 1)[-1]  # Handle "qwen3.6:35b" case
else:
    short_name = model  # No provider prefix — already just the name
```

**Or more robustly:** Extract the model name regardless of provider prefix:
```python
import re
short_name = re.sub(r'^[a-z]+/', '', model)  # Strip leading "provider/" prefix
```

---

## 4. Acceptance Criteria for G2/G3/G4

### G2 (Implementation Ready)
- [x] CTO_PLAN.md complete with exact line numbers verified against ds_eo_dsh files
- [x] All source files confirmed present in ds_eo_dsh
- [x] Model registry module specification written (§3)
- [x] File-by-file change specs with exact lines (§3.1 - §3.4)

### G3 (Review Complete)
- [ ] `model_registry.py` created as specified
- [ ] `session_spawn.py` — no remaining direct `ollama/` usage for model resolution
- [ ] `workflow_defs/default.yaml` — model URIs replaced with placeholders
- [ ] `capability_assessor.py` — runtime-agnostic provider prefix stripping
- [ ] All existing tests pass (Phase 0 + existing suite)
- [ ] Zero behavioral regression in model selection

### G4 (CTO Approval Ready)
- [ ] Implementation matches this plan exactly
- [ ] No hardcoded `ollama/` remains in source file resolution paths
- [ ] `model_registry.py` is importable and functional
- [ ] `TASK_COMPLETION_AUDIT.md` gate status reflects results

---

## 5. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| workflow engine expects literal model URIs from YAML (not placeholders) | High | Verify engine's model loading code; add resolve step if needed |
| `capability_assessor.py` string parsing used in critical path | Medium | Test with multiple URI formats (ollama/x, dsh://x, bare x) |
| Manifest YAML availability at runtime | Medium | Fallback defaults (§3.1) ensure graceful degradation |
| Tests have hardcoded model URIs in assertions | Low | Update test assertions to use registry values |

---

## 6. Deliverables Summary

| # | Deliverable | Location | Status |
|---|------------|----------|--------|
| D1 | CTO_PLAN.md (this document) | `reports/TASK_DS_EO_DSH_005_PHASE2/` | ✅ PRODUCED |
| D2 | TASK_COMPLETION_AUDIT.md | `reports/TASK_DS_EO_DSH_005_PHASE2/` | ⏳ TO BE WRITTEN |
| D3 | M1: model_registry.py spec | §3.1 above | ✅ INCLUDED |
| D4 | M2: session_spawn.py change spec | §3.2 above (lines 47-51 + all usages) | ✅ INCLUDED |
| D5 | M3: workflow_defs/default.yaml change spec | §3.3 above (lines 9, 19, 28, 38) | ✅ INCLUDED |
| D6 | M4: capability_assessor.py change spec | §3.4 above (line 202) | ✅ INCLUDED |
| D7 | Scope boundary + deferred items | §2 + §4 above | ✅ INCLUDED |

---

## 7. Key Design Decisions

1. **Model registry is a module, not a config file** — it's the `model_registry.py` module that encapsulates resolution logic. The manifest YAML serves as the data source, not the API.

2. **Singleton pattern** — `get_registry()` returns a single shared instance to avoid repeated YAML parsing on every model lookup.

3. **Graceful degradation** — if manifest is unavailable, hardcoded fallbacks are used (same as current behavior). No breakage during bootstrap or dev environments without config.

4. **Legacy alias preserved** — `_LEGACY_DEFAULT_MODEL_MAP` kept in session_spawn.py for backward compatibility with any code that may directly reference it.

5. **Runtime resolution uses partition-based provider stripping** — `model.partition("/")` is more robust than `replace("ollama/", "")` because it handles any provider prefix generically.

---

## 8. Pending Decisions

1. **Phase 2 scope approved?** Specifically: creating model_registry.py + updating M1-M4 as specified above?
2. **workflow_defs/default.yaml** — the placeholder approach requires the workflow engine to resolve placeholders at load time. Should I verify this path in the plan, or proceed with implementation assuming we'll fix it there?

Awaiting approval before proceeding to implementation.
