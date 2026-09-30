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
