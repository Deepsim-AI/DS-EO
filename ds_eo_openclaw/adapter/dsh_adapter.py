"""DshRuntimeAdapter - Primary runtime adapter for DeepSeek Harness.

Phase 6: P1 methods replaced with configurable HTTP client implementations.
Each method attempts a real DSH API call first, then falls back gracefully when
the DSH endpoint is not configured or unavailable.
"""

from __future__ import annotations
import json
import os
import logging
from typing import Any, Optional

# Import RuntimeAPI types from sibling module
from .runtime_api import (
    RuntimeAPI, RuntimeModel, RuntimeSession, ActionResult
)
from .dsh_http_client import DshHttpClient

logger = logging.getLogger(__name__)


class DshRuntimeAdapter(RuntimeAPI):
    """
    Adapter for DeepSeek Harness as the primary runtime.

    Phase 6 Status: P1 methods (get_session_info, compact_session, close_session,
    model_info) use configurable HTTP client with graceful fallback.
    
    CONFIGURATION:
        Set environment variable DSH_API_BASE (base URL).
        Optional: DSH_API_TOKEN for auth.
        
    FALLBACK:
        If base_url is empty/unreachable: P1 methods return clear errors or None.
    """

    def __init__(self, base_url: Optional[str] = None):
        self._client = DshHttpClient(
            base_url=base_url or os.environ.get("DSH_API_BASE", ""),
            auth_token=os.environ.get("DSH_API_TOKEN"),
            timeout=30,
        )

    # === Session lifecycle (A1, A3) - P1 methods (Phase 6) ===

    def compact_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        # TODO Phase 1: POST /sessions/{key}/compact
        if not self._client.is_available():
            return ActionResult(
                success=False,
                error=f"DSH API unavailable (no base_url configured)"
            )

        body = {"session_key": session_key}
        if agent_id:
            body["agent_id"] = agent_id

        response = self._client.post(f"/sessions/{session_key}/compact", body=body)

        if response is None:
            return ActionResult(
                success=False,
                error=f"DSH API returned no response for compact_session('{session_key}')"
            )

        context_kb = response.get("context_size_kb", 0)
        tokens_compacted = response.get("tokens_compacted", 0)
        logger.info(f"DSH compact({session_key}) -> success=True, kb={context_kb}")

        return ActionResult(
            success=True,
            details={"context_size_kb": context_kb, "tokens_compacted": tokens_compacted},
        )

    def archive_session(self, session_key: str, agent_id: Optional[str] = None,
                        dest_dir: Optional[str] = None) -> ActionResult:
        # TODO Phase 1: POST /sessions/{key}/export-trajectory
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for archive_session (P2 deferred)"
        )

    def close_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        # TODO Phase 1: DELETE /sessions/{key} or POST /sessions/{key}/close
        if not self._client.is_available():
            return ActionResult(
                success=False,
                error=f"DSH API unavailable (no base_url configured)"
            )

        ok = self._client.delete(f"/sessions/{session_key}")
        if not ok:
            return ActionResult(
                success=False,
                error=f"DSH close_session('{session_key}') failed"
            )

        logger.info(f"DSH close({session_key}) -> success=True")
        return ActionResult(success=True)

    def get_session_info(self, session_key: str, agent_id: Optional[str] = None) -> Optional[RuntimeSession]:
        # TODO Phase 1: GET /sessions/{key}
        if not self._client.is_available():
            return None

        response = self._client.get(f"/sessions/{session_key}")
        if response is None:
            return None

        status_raw = response.get("status", "unknown")
        status_map = {
            "active": "running",
            "idle": "idle",
            "closed": "closed",
            "paused": "paused",
        }
        status = status_map.get(status_raw, status_raw)

        return RuntimeSession(
            key=session_key,
            status=status,
            context_size_bytes=response.get("context_size_bytes", 0),
            turn_count=response.get("turn_count", 0),
            agent_id=None,
            last_turn_time=response.get("last_turn_time"),

        )

    # === Session spawning and task dispatch (A6) - P2 deferred ===

    def spawn_session(self, config: dict) -> ActionResult:
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for spawn_session (P2 deferred)"
        )

    def submit_task(self, task: dict, role: str, plan: Optional[dict] = None) -> ActionResult:
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for submit_task (P2 deferred)"
        )

    def run_tools(self, session_key: str, tool_name: str, tool_args: dict,
                  policy: Optional[dict] = None) -> ActionResult:
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for run_tools (P2 deferred)"
        )

    # === Model registry (A5, A9) - P1 model_info updated in Phase 6 ===

    def model_info(self, model_id: str) -> RuntimeModel:
        # TODO Phase 2: GET /models/{id}
        if self._client.is_available():
            try:
                response = self._client.get(f"/models/{model_id}")
                if response is not None:
                    return RuntimeModel(
                        id=model_id,
                        context_window=response.get("context_window", 0),
                        max_tokens=response.get("max_tokens", 0),
                        gpu_layers=response.get("gpu_layers", -1),
                        ram_bytes=response.get("ram_bytes", 0),
                        provider="dsh",
                    )
            except Exception as e:
                logger.warning(f"DSH model_info({model_id}) catalog query failed: {e}")

        # Fallback to placeholder
        return RuntimeModel(
            id=model_id,
            context_window=0,
            max_tokens=0,
            gpu_layers=-1,
            ram_bytes=0,
            provider="dsh",
        )

    def available_models(self) -> list[RuntimeModel]:
        return []

    # === Generic tool execution (A2, A8) - deferred ===

    def run_task(self, tool: str, args: dict) -> ActionResult:
        return ActionResult(
            success=False,
            error="DSH adapter not yet implemented for run_task (P4 deferred)"
        )

    # === Hooks and bindings (A7) - unchanged in Phase 6 ===

    def register_binding(self, command: str, handler_fn: Any) -> bool:
        return True
