"""OpenClawRuntimeAdapter — Legacy backend adapter wrapping existing OpenClawAPI.

Phase 1+ implementation of the RuntimeAPI interface for the OpenClaw runtime.
All logic is delegated to the existing OpenClawAPI class (ds_eo_dsh/session_health/openclaw_api.py).
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
