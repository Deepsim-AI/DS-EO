"""
DS-EO Dispatcher — Runtime Dispatch Client  (TASK_DS_EO_DSH_015 / Phase 11)

Production bridge that connects the workflow engine (engine.execute_transition)
to a concrete runtime adapter via the RuntimeAPI factory.

This module imports ONLY the RuntimeAPI abstraction boundary
(ds_eo_dsh.adapter.runtime_api.RuntimeAdapterFactory).  It never imports a
concrete adapter directly — the factory resolves the active runtime.

Contract:
    from ds_eo_dsh.dispatcher.dispatch_client import dispatch
    out = dispatch(
        input={"task_id":"TASK_...","target_agent":"cto",
               "transition_name":"G1_APPROVE","payload":"approved"},
        runtime="headless",   # optional; env DSH_ADAPTER else "headless"
    )
    # returns {"result": "<json-transition-result>", "runtime": <name>}

No file-system writes and no governance changes happen here — the adapter
produces artifacts at its own boundary.  The adapter's success/failure is
mapped onto a TransitionResult so the engine can honour it as a gate guard.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Runtime resolution
# --------------------------------------------------------------------------- #

def _resolve_runtime() -> str:
    """Return the runtime name for dispatch.

    Resolution order (see RuntimeAdapterFactory):
      1. DSH_ADAPTER env var, if set
      2. "headless" default — the production DSH headless adapter, which the
         factory selects when no DSH_API_BASE is configured.
    """
    runtime = os.environ.get("DSH_ADAPTER", "headless").strip()
    # Normalise: the factory accepts "dsh"/"openclaw"/"auto"; the headless path
    # is the default when DSH_API_BASE is unset, so "headless" maps to that.
    return runtime


def _build_task_input(dispatch_input: Dict[str, Any]) -> Dict[str, Any]:
    """Build the task dict passed to a runtime adapter's submit_task()."""
    task_id = str(dispatch_input.get("task_id", "")).strip()
    role = str(dispatch_input.get("target_agent", "")).strip()
    transition_name = str(dispatch_input.get("transition_name", "")).strip()
    payload = str(dispatch_input.get("payload", "")).strip()
    from_phase = str(dispatch_input.get("from_phase", "")).strip()
    to_phase = str(dispatch_input.get("to_phase", "")).strip()

    # A task submitted to a runtime must carry an 'instructions' field — this
    # mirrors the adapter's own guard (submit_task requires it).
    instructions = payload or transition_name or task_id
    if not instructions:
        instructions = "Execute the requested workflow transition."

    return {
        "instructions": instructions,
        "task_id": task_id,
        "target_agent": role,
        "transition_name": transition_name,
        "from_phase": from_phase,
        "to_phase": to_phase,
        # Legacy adapter hint kept for compatibility with existing submit_task.
        "instructions": instructions or task_id,
    }


def _normalize_role(role: str) -> str:
    """Lower-case a role for use as the adapter's 'role' argument."""
    return role.strip().lower() if role else ""


def _build_transition_result(
    ok: bool,
    error: Optional[str],
    runtime_name: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Serialize a TransitionResult-shaped dict for the engine to consume."""
    return {
        "success": ok,
        "error": error,
        "runtime": runtime_name,
        "details": details or {},
    }


def run(dispatch_input: Dict[str, Any], runtime: Optional[str] = None) -> Dict[str, Any]:
    """Execute a runtime dispatch for a single transition/role.

    Args:
        dispatch_input: dict with task_id, target_agent(+role), transition_name,
                        payload, from_phase, to_phase (any subset is acceptable).
        runtime: explicit runtime override.  None -> env / default headless.

    Returns:
        {"result": str (json TransitionResult), "runtime": str}
    """
    if not isinstance(dispatch_input, dict) or not dispatch_input:
        payload = _build_transition_result(
            ok=False,
            error="dispatch input must be a non-empty dict",
            runtime=_resolve_runtime(),
        )
        return {"result": json.dumps(payload), "runtime": payload["runtime"]}

    # --- resolve runtime ---------------------------------------------------- #
    runtime_name = (runtime or _resolve_runtime()).lower().strip()
    if not runtime_name:
        runtime_name = "headless"

    try:
        # Import the RuntimeAPI factory — production boundary layer.
        from ds_eo_dsh.adapter.runtime_api import RuntimeAdapterFactory
    except Exception as exc:  # pragma: no cover — defensive
        logger.error("Failed to import RuntimeAdapterFactory during dispatch: %s", exc)
        payload = _build_transition_result(
            ok=False, error=f"RuntimeAdapterFactory import failed: {exc}",
            runtime=runtime_name,
        )
        return {"result": json.dumps(payload), "runtime": payload["runtime"]}

    # --- map our runtime token into the factory's vocabulary ---------------- #
    # "headless" is our default token; the factory selects the production
    # headless adapter when no DSH_API_BASE is configured.
    factory_runtime = runtime_name
    if factory_runtime in ("headless", None):
        factory_runtime = "dsh"  # factory picks headless unless DSH_API_BASE set
    elif factory_runtime in ("openclaw", "auto", "dsh"):
        pass  # pass through unchanged

    try:
        adapter = RuntimeAdapterFactory.create(runtime=factory_runtime)
    except Exception as exc:
        logger.error("Failed to create runtime adapter (%s): %s", factory_runtime, exc)
        payload = _build_transition_result(
            ok=False, error=f"Failed to create runtime adapter: {exc}",
            runtime=runtime_name,
        )
        return {"result": json.dumps(payload), "runtime": payload["runtime"]}

    # --- build task + dispatch --------------------------------------------- #
    task = _build_task_input(dispatch_input)
    role = _normalize_role(task.get("target_agent") or task.get("role") or "")
    payload_text = str(dispatch_input.get("payload") or dispatch_input.get("transition_name")
                       or dispatch_input.get("task_id") or "Execute the requested transition.")
    task["instructions"] = payload_text

    try:
        action_result = adapter.submit_task(task=task, role=role)
    except Exception as exc:
        logger.error("submit_task raised for role=%s: %s", role, exc)
        payload = _build_transition_result(
            ok=False, error=f"submit_task raised: {exc}", runtime=runtime_name,
        )
        return {"result": json.dumps(payload), "runtime": payload["runtime"]}

    # --- map ActionResult onto a TransitionResult --------------------------- #
    info = getattr(action_result, "details", {}) or {}
    if getattr(action_result, "success", False):
        details = {
            "task_id": info.get("task_id"),
            "role": info.get("role", role),
            "model_used": info.get("model_used"),
            "output_text": str(info.get("output_text", "")[:500]),
        }
        logger.info("Dispatch succeeded for role=%s (runtime=%s).", role, runtime_name)
    else:
        details = {
            "task_id": info.get("task_id"),
            "role": info.get("role", role),
            "partial_output": str(info.get("partial_output") or ""),
        }
        logger.warning("Dispatch failed for role=%s (runtime=%s): %s",
                       role, runtime_name, action_result.error)

    payload = _build_transition_result(
        ok=bool(getattr(action_result, "success", False)),
        error=action_result.error,
        runtime=runtime_name,
        details=details,
    )
    return {"result": json.dumps(payload), "runtime": payload["runtime"]}
