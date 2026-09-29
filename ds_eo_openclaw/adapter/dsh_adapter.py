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
