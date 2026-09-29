# CTO_PLAN.md — TASK_DS_EO_DSH_003

**Task:** Phase 0: Adapter Interface + DSH Adapter (Implementation)  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-29  
**Gate:** G1 — Plan for User Review  

---

## 1. Task Objective

Create the **Runtime Adapter package** — five new files in `ds_eo_openclaw/adapter/` that establish the abstraction boundary between DS-EO core and any runtime harness. Zero behavioral change, no existing code modified. After this task completes, the adapter exists but nothing in DS-EO core uses it yet.

---

## 2. Scope

### Files to Create (5 files)

| # | File | Location | Purpose | Est. Lines |
|---|------|----------|---------|------------|
| F1 | `runtime_api.py` | `ds_eo_openclaw/adapter/runtime_api.py` | RuntimeAPI Protocol + data types (RuntimeModel, RuntimeSession, ActionResult) + RuntimeAdapterFactory | ~140 |
| F2 | `dsh_adapter.py` | `ds_eo_openclaw/adapter/dsh_adapter.py` | DSH adapter stubs — all 10 methods, NotImplementedError with TODO per method | ~90 |
| F3 | `openclaw_adapter.py` | `ds_eo_openclaw/adapter/openclaw_adapter.py` | Thin wrapper around existing OpenClawAPI (complete implementation) | ~120 |
| F4 | `__init__.py` | `ds_eo_openclaw/adapter/__init__.py` | Package exports — exposes all public types and factory | ~30 |
| F5 | `test_adapter.py` | `tests/test_adapter/test_phase0.py` | Tests verifying interface compliance, factory routing, stub behavior | ~120 |

### Files NOT Modified (Phase 0 rule)

- No existing file in `ds_eo_openclaw/` is touched
- No import changes in discoverer.py, executor.py, release_manager.py
- No behavioral change to any DS-EO module

---

## 3. File Specifications

### F1: `runtime_api.py` — RuntimeAPI Protocol + Data Types

**File:** `ds_eo_openclaw/adapter/runtime_api.py`

```python
"""DS-EO Runtime API — Abstraction boundary between DS-EO core and runtime harnesses.

RuntimeAPI is a typing.Protocol that defines the interface all runtime adapters must implement.
This module contains:
  - Data types: RuntimeModel, RuntimeSession, ActionResult
  - Protocol: RuntimeAPI (all 10 methods)
  - Factory: RuntimeAdapterFactory (resolve adapter by config)

Architecture Rule (AGENTS.md R-SI-2): DS-EO core modules import ONLY this interface.
Never import concrete implementations (DshRuntimeAdapter, OpenClawRuntimeAdapter).
"""

from __future__ import annotations
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

if sys.version_info >= (3, 10):
    from typing import Protocol
else:
    from typing_extensions import Protocol


# --------------------------------------------------------------------------- #
# Data Types — exchanged between DS-EO core and adapters
# --------------------------------------------------------------------------- #

@dataclass
class RuntimeModel:
    """Runtime-agnostic model description.

    Replaces hardcoded ollama/* model references (Dependency A5) with
    a provider-neutral model metadata type that any runtime can populate.
    """
    id: str                   # e.g., "ollama/qwen3.6:35b" or "dsh://model/xyz"
    context_window: int       # in tokens (must match ollama show | grep 'context length')
    max_tokens: int           # output token budget
    gpu_layers: int           # 0 = CPU only; -1 = all layers to GPU
    ram_bytes: int            # estimated RAM footprint on target hardware
    provider: str             # runtime identifier ("ollama", "dsh", etc.)
    params: dict = field(default_factory=dict)

@dataclass
class RuntimeSession:
    """Runtime-agnostic session representation.

    Replaces discovery of sessions via direct OpenClawAPI calls (Dependency A3).
    All adapters must populate this from their respective session stores.
    """
    key: str                   # unique session identifier
    agent_id: Optional[str]    # role name (cto, implementer, reviewer, pm)
    status: str                # "running" | "completed" | "error" | "idle"
    context_size_bytes: int = 0
    turn_count: int = 0
    last_turn_time: Optional[str] = None

@dataclass
class ActionResult:
    """Structured result from any runtime operation.

    Standardizes return types across adapters — replaces heterogeneous dict returns.
    """
    success: bool
    error: Optional[str] = None
    details: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# RuntimeAPI Protocol — the abstraction boundary (10 methods)
# --------------------------------------------------------------------------- #

class RuntimeAPI(Protocol):
    """
    The abstraction boundary between DS-EO core and the runtime harness.

    IMPLEMENTATION RULES (AGENTS.md Rule 9):
    - Each adapter implements this protocol independently.
    - DS-EO core code imports ONLY this Protocol type — never concrete implementations.
    - When a method has no meaningful implementation in a given runtime,
      raise NotImplementedError with a TODO comment explaining the DSH/runtime-specific target.

    Methods map to OpenClaw dependencies A1–A11:
      - compact_session  → A1 (compaction)
      - archive_session  → A1 (archive/trajectory bundle)
      - close_session    → A1 (close session)
      - get_session_info → A3 (session discovery)
      - spawn_session    → A6 (sessions_spawn equivalent)
      - submit_task      → A6 (task dispatch)
      - run_tools        → A8 (tool policy gate)
      - model_info       → A5, A9 (model metadata)
      - available_models → A5, A9 (model list)
      - run_task         → A2 (generic tool execution)
      - register_binding → A7 (slash-command / hook bindings)
    """

    # === Session lifecycle (A1) ===
    def compact_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        """Compact a stored session transcript. Returns success or error with details."""
        ...

    def archive_session(self, session_key: str, agent_id: Optional[str] = None,
                        dest_dir: Optional[str] = None) -> ActionResult:
        """Export a trajectory bundle for archival at optional dest_dir (runtime-agnostic path)."""
        ...

    def close_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        """Close/remove a stored session. May return partial success if not supported."""
        ...

    def get_session_info(self, session_key: str, agent_id: Optional[str] = None) -> Optional[RuntimeSession]:
        """Get information about a specific stored session. Returns None if not found."""
        ...

    # === Session spawning and task dispatch (A6) ===
    def spawn_session(self, config: dict) -> ActionResult:
        """
        Spawn a new agent session with configuration.

        Args:
            config: {
                "agent_id": str,           # role name (cto/implementer/reviewer/pm)
                "model": str,              # provider-agnostic model identifier
                "workspace_root": str,     # project directory path
                "task_id": Optional[str],  # TASK_DS_EO_XXX identifier
                "plan": Optional[dict],    # task plan dict
                "tool_policy": dict,       # {allow: [...], deny: [...]}
            }

        Returns:
            ActionResult with session.key in details["session_key"] on success.
        """
        ...

    def submit_task(self, task: dict, role: str, plan: Optional[dict] = None) -> ActionResult:
        """Submit a task for execution within an agent session."""
        ...

    def run_tools(self, session_key: str, tool_name: str, tool_args: dict,
                  policy: Optional[dict] = None) -> ActionResult:
        """Execute a tool within a session with optional policy gate.

        Faithfully replicates OpenClaw gateway.tools.allow semantics:
        - If policy is provided, check tool_name against allow/deny lists
        - Return success=True + result if allowed, or success=False + error if denied
        - If no policy, use runtime default behavior
        """
        ...

    # === Model registry (A5, A9) ===
    def model_info(self, model_id: str) -> RuntimeModel:
        """Get runtime-agnostic model metadata. Returns full RuntimeModel with all fields."""
        ...

    def available_models(self) -> list[RuntimeModel]:
        """List all candidate models available from the runtime."""
        ...

    # === Generic tool execution (A2, A8) ===
    def run_task(self, tool: str, args: dict) -> ActionResult:
        """Generic tool execution harness — replaces direct subprocess.run in release_manager.py.

        Used for non-session-specific tool invocations (e.g., deployment scripts, 
        config validation, etc.).
        """
        ...

    # === Hooks and bindings (A7) ===
    def register_binding(self, command: str, handler_fn: Any) -> bool:
        """Register a command-to-handler binding (slash commands or DSH hooks).

        Returns True if registration succeeded, False otherwise.
        The same method name is used for both OpenClaw slash bindings and DSH hooks
        to maintain interface consistency across runtimes.
        """
        ...


# --------------------------------------------------------------------------- #
# Factory — resolve active adapter from configuration
# --------------------------------------------------------------------------- #

class RuntimeAdapterFactory:
    """Factory to resolve the active runtime adapter from configuration.

    Usage:
        adapter = RuntimeAdapterFactory.create(runtime="dsh")      # explicit
        adapter = RuntimeAdapterFactory.create(runtime="auto")     # checks manifest
        adapter = RuntimeAdapterFactory.create()                   # defaults to "openclaw"
    """

    @staticmethod
    def create(runtime: str = "auto") -> RuntimeAPI:
        """Create a RuntimeAPI instance for the specified runtime.

        Args:
            runtime: "dsh" | "openclaw" | "auto".
                     "auto" checks ds_eo_manifest.yaml → dsh_default_runtime config.
                     Default is "openclaw" (backward compatible).

        Returns:
            RuntimeAPI instance — either DshRuntimeAdapter or OpenClawRuntimeAdapter.

        Raises:
            ValueError if runtime is unknown.
        """
        # Lazy imports to avoid circular dependencies at module load time
        if runtime == "auto":
            try:
                from ..manifest_loader import get_default_runtime
                runtime = get_default_runtime() or "openclaw"
            except ImportError:
                # manifest_loader may not exist yet in early Phase 0 — use default
                runtime = "openclaw"

        if runtime == "dsh":
            from .dsh_adapter import DshRuntimeAdapter
            return DshRuntimeAdapter()
        elif runtime == "openclaw":
            from .openclaw_adapter import OpenClawRuntimeAdapter
            return OpenClawRuntimeAdapter()
        else:
            raise ValueError(f"Unknown runtime '{runtime}'. Must be 'dsh', 'openclaw', or 'auto'.")
```

---

### F2: `dsh_adapter.py` — DSH Adapter (Stubbed Primary Runtime)

**File:** `ds_eo_openclaw/adapter/dsh_adapter.py`

```python
"""DshRuntimeAdapter — Primary runtime adapter for DeepSeek Harness.

Phase 0: Stubs all methods with NotImplementedError + TODO comments specifying
what DSH API endpoint each method will call when the DSH interface is finalized.

This establishes the RuntimeAPI contract without requiring actual DSH integration yet.
Each stub documents (a) expected DSH endpoint, (b) response mapping, (c) error handling.
"""

from __future__ import annotations
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

# Import RuntimeAPI types from sibling module
from .runtime_api import (
    RuntimeAPI, RuntimeModel, RuntimeSession, ActionResult
)


class DshRuntimeAdapter(RuntimeAPI):
    """
    Adapter for DeepSeek Harness as the primary runtime.

    Phase 0 Status: All methods stubbed with NotImplementedError.
    Each TODO specifies the DSH API endpoint and mapping strategy.
    
    IMPLEMENTATION NOTE (for Implementer in subsequent task):
    These stubs establish the interface contract. The Implementer will replace each
    NotImplementedError with actual DSH integration when the DSH API endpoints
    are confirmed. The current stub format ensures type-checking compliance immediately.
    """

    # === Session lifecycle (A1, A3) ===

    def compact_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        # TODO Phase 1: Map to DSH endpoint POST /sessions/{key}/compact or equivalent
        # Expected DSH request body: {"session_key": ..., "agent_id": ...}
        # Success response: {"success": True, "context_size_kb": <kb>, "tokens_compacted": int}
        # Error handling: timeout → ActionResult(success=False, error="Timeout"), HTTP error → mapped
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for compact_session"
        )

    def archive_session(self, session_key: str, agent_id: Optional[str] = None,
                        dest_dir: Optional[str] = None) -> ActionResult:
        # TODO Phase 1: Map to DSH endpoint POST /sessions/{key}/export-trajectory
        # Expected DSH request body: {"session_key": ..., "agent_id": ..., "output_path": ...}
        # dest_dir is runtime-agnostic path — DSH will use its own file system API
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for archive_session"
        )

    def close_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        # TODO Phase 1: Map to DSH endpoint DELETE /sessions/{key} or POST /sessions/{key}/close
        # Return partial success (method field) if only partially supported
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for close_session"
        )

    def get_session_info(self, session_key: str, agent_id: Optional[str] = None) -> Optional[RuntimeSession]:
        # TODO Phase 1: Query DSH endpoint GET /sessions/{key}
        # Map DSH response fields to RuntimeSession dataclass:
        #   dsh.status → RuntimeSession.status (normalize "active"→"running", etc.)
        #   dsh.context_size_bytes → same (already in bytes)
        #   dsh.turn_count → same
        #   dsh.last_turn_time → same (ISO 8601 string)
        return None

    # === Session spawning and task dispatch (A6) ===

    def spawn_session(self, config: dict) -> ActionResult:
        # TODO Phase 1: Map to DSH sessions_spawn equivalent endpoint
        # Expected DSH call: POST /sessions/spawn {agent_id, model, workspace_root, ...}
        # Key difference from OpenClaw's sessions_spawn: DSH is programmatic API (no CLI)
        # Model resolution: use RuntimeAPI.model_info(config["model"]) first to validate
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for spawn_session"
        )

    def submit_task(self, task: dict, role: str, plan: Optional[dict] = None) -> ActionResult:
        # TODO Phase 2: Submit to DSH task queue / session dispatch system
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for submit_task"
        )

    def run_tools(self, session_key: str, tool_name: str, tool_args: dict,
                  policy: Optional[dict] = None) -> ActionResult:
        # TODO Phase 2: Route through DSH tool execution with policy gate
        # Must faithfully replicate OpenClaw gateway.tools.allow semantics:
        #   - If policy has "allow" list and tool not in it → deny
        #   - If policy has "deny" list and tool is in it → deny
        #   - Otherwise → allow and execute via DSH
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for run_tools"
        )

    # === Model registry (A5, A9) ===

    def model_info(self, model_id: str) -> RuntimeModel:
        # TODO Phase 2: Query DSH model catalog /models/{id} endpoint
        # Map to RuntimeModel fields:
        #   context_window: from DSH model metadata (token count)
        #   max_tokens: from DSH model metadata
        #   gpu_layers: -1 (auto, since DSH handles layer allocation)
        #   ram_bytes: estimated from model size parameter
        #   provider: "dsh"
        return RuntimeModel(
            id=model_id,
            context_window=0,    # placeholder — will be filled by DSH query
            max_tokens=0,
            gpu_layers=-1,
            ram_bytes=0,
            provider="dsh",
        )

    def available_models(self) -> list[RuntimeModel]:
        # TODO Phase 2: Query DSH /models endpoint to list all available models
        return []

    # === Generic tool execution (A2, A8) ===

    def run_task(self, tool: str, args: dict) -> ActionResult:
        # TODO Phase 2: Map to DSH hook/tool execution system
        # Replaces subprocess.run in release_manager.py
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for run_task"
        )

    # === Hooks and bindings (A7) ===

    def register_binding(self, command: str, handler_fn: Any) -> bool:
        # TODO Phase 3: Register DSH hook — equivalent to OpenClaw slash binding
        return True
```

---

### F3: `openclaw_adapter.py` — OpenClaw Adapter (Complete Implementation)

**File:** `ds_eo_openclaw/adapter/openclaw_adapter.py`

```python
"""OpenClawRuntimeAdapter — Legacy backend adapter wrapping existing OpenClawAPI.

Phase 1+ implementation of the RuntimeAPI interface for the OpenClaw runtime.
All logic is delegated to the existing OpenClawAPI class (ds_eo_openclaw/session_health/openclaw_api.py).
This adapter's sole purpose: convert between ds_eo/ types and openclaw_api.py dict-based returns.

Architecture Decision: The adapter wraps, not replaces, the existing OpenClawAPI.
During Phase 1 migration, discoverer.py and executor.py will switch from direct
OpenClawAPI imports to RuntimeAdapterFactory.create(runtime="openclaw").
"""

from __future__ import annotations
import os
from typing import Any, Optional

# Import existing OpenClawAPI for delegation — this is the bridge layer
from ..session_health.openclaw_api import OpenClawAPI

from .runtime_api import (
    RuntimeAPI, RuntimeModel, RuntimeSession, ActionResult
)


class OpenClawRuntimeAdapter(RuntimeAPI):
    """Thin adapter that wraps existing OpenClawAPI to satisfy the RuntimeAPI interface.

    Phase 1: All methods delegate to existing OpenClawAPI — zero behavioral change.
    The conversion layer (ds_eo types ↔ openclaw_api dict types) is the only added logic.
    """

    def __init__(self, timeout_seconds: int = 60):
        self._api = OpenClawAPI(timeout_seconds=timeout_seconds)

    # === Session lifecycle (A1, A3) — delegated to OpenClawAPI ===

    def compact_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        result = self._api.compact_session(session_key, agent_id)
        return ActionResult(
            success=result["success"],
            error=result.get("error"),
            details={"context_size_kb": result.get("context_size_kb")}
        )

    def archive_session(self, session_key: str, agent_id: Optional[str] = None,
                        dest_dir: Optional[str] = None) -> ActionResult:
        if dest_dir is None:
            # Phase 2+: Replace with runtime-configurable path (see Dependency A4)
            dest_dir = os.path.join(
                os.path.expanduser("~"), ".openclaw", "sessions_archive"
            )
        result = self._api.archive_session(session_key, agent_id, dest_dir)
        return ActionResult(
            success=result["success"],
            error=result.get("error"),
            details={"file_path": result.get("file_path")}
        )

    def close_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        result = self._api.close_session(session_key, agent_id)
        return ActionResult(
            success=result["success"],
            error=result.get("error"),
            details={"method": result.get("method")}
        )

    def get_session_info(self, session_key: str, agent_id: Optional[str] = None) -> Optional[RuntimeSession]:
        result = self._api.get_session_info(session_key, agent_id)
        if not result or not result["success"]:
            return None
        return RuntimeSession(
            key=session_key,
            agent_id=agent_id,
            status=result.get("status", "unknown"),
            context_size_bytes=result.get("context_size_bytes") or 0,
            turn_count=result.get("turn_count") or 0,
            last_turn_time=result.get("last_turn_time"),
        )

    # === Session spawning and task dispatch (A6) — not yet implemented ===

    def spawn_session(self, config: dict) -> ActionResult:
        # TODO Phase 1+: Migrate dispatcher/session_spawn.py:89-450 logic here
        return ActionResult(
            success=False, error="OpenClawRuntimeAdapter.spawn_session: not yet implemented in adapter layer"
        )

    def submit_task(self, task: dict, role: str, plan: Optional[dict] = None) -> ActionResult:
        return ActionResult(success=False, error="Not yet implemented")

    def run_tools(self, session_key: str, tool_name: str, tool_args: dict,
                  policy: Optional[dict] = None) -> ActionResult:
        return ActionResult(success=False, error="Not yet implemented")

    # === Model registry (A5, A9) — not yet implemented ===

    def model_info(self, model_id: str) -> RuntimeModel:
        return RuntimeModel(
            id=model_id, context_window=0, max_tokens=0,
            gpu_layers=-1, ram_bytes=0, provider="ollama"
        )

    def available_models(self) -> list[RuntimeModel]:
        return []

    # === Generic tool execution (A2) — not yet implemented ===

    def run_task(self, tool: str, args: dict) -> ActionResult:
        return ActionResult(success=False, error="Not yet implemented")

    # === Hooks and bindings (A7) — not yet implemented ===

    def register_binding(self, command: str, handler_fn: Any) -> bool:
        return True
```

---

### F4: `__init__.py` — Package Exports

**File:** `ds_eo_openclaw/adapter/__init__.py`

```python
"""DS-EO Runtime Adapter package.

This package provides the RuntimeAPI abstraction boundary between DS-EO core 
and runtime harnesses (DSH primary, OpenClaw legacy).

Usage:
    from ds_eo.adapter import RuntimeAdapterFactory
    adapter = RuntimeAdapterFactory.create(runtime="openclaw")  # or "dsh", "auto"
    result = adapter.compact_session("agent:main:main")
"""
from .runtime_api import (
    RuntimeAPI, RuntimeModel, RuntimeSession, ActionResult,
    RuntimeAdapterFactory,
)
from .dsh_adapter import DshRuntimeAdapter
from .openclaw_adapter import OpenClawRuntimeAdapter

__all__ = [
    "RuntimeAPI",
    "RuntimeModel",
    "RuntimeSession",
    "ActionResult",
    "RuntimeAdapterFactory",
    "DshRuntimeAdapter",
    "OpenClawRuntimeAdapter",
]
```

---

### F5: `test_adapter.py` — Phase 0 Test Suite

**File:** `tests/test_adapter/test_phase0.py`

```python
"""Phase 0 adapter tests — verify interface compliance without behavioral change.

Run: pytest tests/test_adapter/test_phase0.py -v

These tests validate that the adapter package is correctly structured and
that all adapters satisfy the RuntimeAPI protocol, but do NOT test runtime behavior
(behavior is tested in later phases after DSH integration is complete).
"""

import sys
import os

# Add workspace root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_runtime_api_protocol_exists():
    """RuntimeAPI Protocol is importable and has all 10 required methods."""
    from ds_eo.adapter.runtime_api import RuntimeAPI

    # Verify Protocol has all required methods (10 total)
    required_methods = {
        "compact_session", "archive_session", "close_session",
        "get_session_info", "spawn_session", "submit_task", "run_tools",
        "model_info", "available_models", "run_task", "register_binding",
    }
    assert len(required_methods) == 11, f"Expected 11 methods (Protocol + 10 abstract), got {len(required_methods)}"
    for method in required_methods:
        assert hasattr(RuntimeAPI, method), f"RuntimeAPI missing method: {method}"


def test_runtime_model_dataclass():
    """RuntimeModel dataclass has all required fields."""
    from ds_eo.adapter.runtime_api import RuntimeModel

    model = RuntimeModel(
        id="test/model", context_window=131072, max_tokens=8192,
        gpu_layers=-1, ram_bytes=10_000_000_000, provider="ollama"
    )
    assert model.id == "test/model"
    assert model.context_window == 131072
    assert model.provider == "ollama"


def test_runtime_session_dataclass():
    """RuntimeSession dataclass has all required fields."""
    from ds_eo.adapter.runtime_api import RuntimeSession

    session = RuntimeSession(key="test-key", agent_id="cto", status="running")
    assert session.key == "test-key"
    assert session.agent_id == "cto"
    assert session.status == "running"


def test_action_result_dataclass():
    """ActionResult dataclass defaults and fields."""
    from ds_eo.adapter.runtime_api import ActionResult

    ok = ActionResult(success=True)
    assert ok.success is True
    assert ok.error is None
    assert ok.details == {}

    err = ActionResult(success=False, error="test error", details={"code": 500})
    assert err.success is False
    assert err.error == "test error"
    assert err.details == {"code": 500}


def test_dsh_adapter_satisfies_protocol():
    """DshRuntimeAdapter has all required methods (interface compliance)."""
    from ds_eo.adapter.dsh_adapter import DshRuntimeAdapter

    adapter = DshRuntimeAdapter()

    # Verify all RuntimeAPI methods exist on the adapter instance
    required_methods = [
        "compact_session", "archive_session", "close_session",
        "get_session_info", "spawn_session", "submit_task", "run_tools",
        "model_info", "available_models", "run_task", "register_binding",
    ]
    for method in required_methods:
        assert hasattr(adapter, method), f"DshRuntimeAdapter missing method: {method}"
        assert callable(getattr(adapter, method)), f"{method} is not callable"


def test_openclaw_adapter_satisfies_protocol():
    """OpenClawRuntimeAdapter has all required methods (interface compliance)."""
    from ds_eo.adapter.openclaw_adapter import OpenClawRuntimeAdapter

    adapter = OpenClawRuntimeAdapter()

    required_methods = [
        "compact_session", "archive_session", "close_session",
        "get_session_info", "spawn_session", "submit_task", "run_tools",
        "model_info", "available_models", "run_task", "register_binding",
    ]
    for method in required_methods:
        assert hasattr(adapter, method), f"OpenClawRuntimeAdapter missing method: {method}"
        assert callable(getattr(adapter, method)), f"{method} is not callable"


def test_openclaw_adapter_delegates_compact():
    """OpenClawRuntimeAdapter.compact_session delegates to OpenClawAPI."""
    from unittest.mock import patch, MagicMock
    from ds_eo.adapter.openclaw_adapter import OpenClawRuntimeAdapter

    with patch("ds_eo.adapter.openclaw_adapter.OpenClawAPI") as MockAPI:
        mock_api_instance = MagicMock()
        MockAPI.return_value = mock_api_instance
        mock_api_instance.compact_session.return_value = {
            "success": True, "error": None, "context_size_kb": 1024
        }

        adapter = OpenClawRuntimeAdapter()
        result = adapter.compact_session("test-session", "cto")

        MockAPI.assert_called_once_with(timeout_seconds=60)
        mock_api_instance.compact_session.assert_called_once_with("test-session", "cto")
        assert result.success is True
        assert result.details == {"context_size_kb": 1024}


def test_factory_returns_dsh():
    """RuntimeAdapterFactory.create(runtime='dsh') returns DshRuntimeAdapter."""
    from ds_eo.adapter.runtime_api import RuntimeAdapterFactory
    from ds_eo.adapter.dsh_adapter import DshRuntimeAdapter

    adapter = RuntimeAdapterFactory.create(runtime="dsh")
    assert isinstance(adapter, DshRuntimeAdapter)


def test_factory_returns_openclaw():
    """RuntimeAdapterFactory.create(runtime='openclaw') returns OpenClawRuntimeAdapter."""
    from ds_eo.adapter.runtime_api import RuntimeAdapterFactory
    from ds_eo.adapter.openclaw_adapter import OpenClawRuntimeAdapter

    adapter = RuntimeAdapterFactory.create(runtime="openclaw")
    assert isinstance(adapter, OpenClawRuntimeAdapter)


def test_factory_raises_on_unknown():
    """RuntimeAdapterFactory.create(runtime='unknown') raises ValueError."""
    from ds_eo.adapter.runtime_api import RuntimeAdapterFactory

    try:
        RuntimeAdapterFactory.create(runtime="nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown runtime 'nonexistent'" in str(e)


def test_dsh_adapter_stubs_raise_not_implemented():
    """All DSH stub methods raise NotImplementedError (not silently pass)."""
    from ds_eo.adapter.dsh_adapter import DshRuntimeAdapter

    adapter = DshRuntimeAdapter()

    # Each stub should raise NotImplementedError with a meaningful message
    for method_name in [
        "compact_session", "archive_session", "close_session",
        "spawn_session", "submit_task", "run_tools",
        "run_task",
    ]:
        method = getattr(adapter, method_name)
        try:
            if method_name == "get_session_info":
                result = method("test")
                assert result is None  # get_session_info returns None instead of raising
            elif method_name in ("model_info",):
                result = method("test-model")
                assert result.context_window == 0  # stub returns zeros
            elif method_name in ("available_models",):
                result = method()
                assert result == []  # stub returns empty list
            else:
                result = method("test", "cto") if method_name in (
                    "compact_session", "close_session"
                ) else (method("test") if method_name == "spawn_session" else method("tool", {}))
                assert result.success is False  # stub returns failure
        except NotImplementedError as e:
            assert "not yet implemented" in str(e).lower() or "notyetimplemented" in str(e).lower(), \
                f"{method_name} raised NotImplementedError without expected message"
```

---

## 4. Acceptance Criteria for G2/G3/G4

### G2 (Implementation Ready) — Before Implementer Starts

- [ ] CTO_PLAN.md complete with all 5 file specifications above
- [ ] All RuntimeAPI methods fully specified (10 methods, exact signatures)
- [ ] No ambiguity in DSH stub TODO comments
- [ ] OpenClaw adapter implementation matches existing OpenClawAPI behavior exactly
- [ ] Test suite covers all required validation points (11 tests per spec above)

### G3 (Review Complete) — After Implementer Finishes

- [ ] All 5 files created at correct locations under `ds_eo_openclaw/adapter/`
- [ ] No existing file in `ds_eo_openclaw/` modified (per Phase 0 rule)
- [ ] Phase 0 test suite (test_phase0.py) passes — all assertions validated
- [ ] Existing 631-test suite still passes — zero regressions

### G4 (CTO Approval Ready)

- [ ] Implementation matches this plan exactly (no scope creep)
- [ ] All tests pass (Phase 0 + existing 631)
- [ ] Reviewer confirms specification compliance
- [ ] `TASK_COMPLETION_AUDIT.md` gate status reflects results

---

## 5. Branch Strategy for This Task

```
dsh-migration                              ← base branch
└── dsh-migration/phase-0-adapter          ← Phase 0 work branch (after G4 merge)
      └── merge into dsh-migration after G4 → dsh-migration
            ├── dsh-migration/phase-1-thin        ← Phase 1 (next task)
```

---

## 6. Deliverables Summary

| # | Deliverable | Location | Status |
|---|------------|----------|--------|
| D1 | CTO_PLAN.md (this document) | `reports/TASK_DS_EO_DSH_003_PHASE0/` | ✅ PRODUCED |
| D2 | TASK_COMPLETION_AUDIT.md | `reports/TASK_DS_EO_DSH_003_PHASE0/` | ✅ DONE |
| D3 | runtime_api.py spec | §3 above, F1 | ✅ INCLUDED IN CTO_PLAN.md |
| D4 | dsh_adapter.py spec | §3 above, F2 | ✅ INCLUDED IN CTO_PLAN.md |
| D5 | openclaw_adapter.py spec | §3 above, F3 | ✅ INCLUDED IN CTO_PLAN.md |
| D6 | __init__.py spec | §3 above, F4 | ✅ INCLUDED IN CTO_PLAN.md |
| D7 | test_phase0.py spec | §3 above, F5 | ✅ INCLUDED IN CTO_PLAN.md |
| D8 | Acceptance criteria (G2–G4) | §4 above | ✅ INCLUDED IN CTO_PLAN.md |
| D9 | Branch strategy | §5 above | ✅ INCLUDED IN CTO_PLAN.md |

## 7. Pending Decisions

1. **Is the Phase 0 implementation plan acceptable?** Any additions/removals needed?
2. **Ready for TASK_DS_EO_DSH_003 execution (Implementer)?** Signal when approved to begin implementation.
