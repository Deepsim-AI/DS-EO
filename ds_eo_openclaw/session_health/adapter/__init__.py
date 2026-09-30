# DS-EO Session Health — runtime-adapter package (Phase 1 + Phase 2).

"""Runtime-adapter facade for DS-EO session health.

This package is the sole seam between DS-EO business logic (discoverer,
classifier, monitor, executor, audit) and any concrete agent runtime.

The primary runtime is :class:`.dsh_adapter.DshRuntimeAdapter`; the read-only
legacy backend is :class:`.openclaw_adapter.OpenClawRuntimeAdapter`. DS-EO core
code imports from this package and depends on the :class:`.runtime_api.RuntimeAPI`
contract — never on ``subprocess`` or OpenClaw primitives directly.

Default selection (see :func:`default_runtime`) is the **DSH** backend;
``OPENCLAW_ONLY`` or an explicit adapter can select the legacy path.
"""

from .runtime_api import (
    ActionResult,
    RuntimeAPI,
    RuntimeModel,
    RuntimeSessionId,
    RuntimeError,
    SessionInfo,
    ToolPolicy,
    ToolResult,
)
from .openclaw_adapter import OpenClawRuntimeAdapter
from .dsh_adapter import DshRuntimeAdapter

__all__ = [
    # runtime-independent interface
    "RuntimeAPI",
    "RuntimeSessionId",
    "RuntimeModel",
    "ToolPolicy",
    "ToolResult",
    "ActionResult",
    "SessionInfo",
    "RuntimeError",
    # concrete adapters
    "OpenClawRuntimeAdapter",
    "DshRuntimeAdapter",
]
