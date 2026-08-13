"""
DS-EO Dispatcher — Unified Dispatch Interface.
"""

from .registry import AgentRegistry
from .engine import WorkflowEngine, TransitionRecord, TransitionResult
from .state_manager import TaskStateManager, TransitionSnapshot, PendingWorkSnapshot
from .session_spawn import SessionSpawnManager, spawn_agent, SpawnOutcome
from .session_dispatch.engine import SessionDispatcher, SpawnResult as DispatchSpawnResult

__all__ = [
    "AgentRegistry",
    "WorkflowEngine",
    "TransitionRecord",
    "TransitionResult",
    "TaskStateManager",
    "TransitionSnapshot",
    "PendingWorkSnapshot",
    "SessionSpawnManager",
    "spawn_agent",
    "SpawnOutcome",
    "SessionDispatcher",
    "DispatchSpawnResult",
]
