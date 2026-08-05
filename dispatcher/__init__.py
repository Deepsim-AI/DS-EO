"""
DS-EO Dispatcher — Unified Dispatch Interface.
"""

from .registry import AgentRegistry
from .engine import WorkflowEngine, TransitionRecord, TransitionResult
from .state_manager import TaskStateManager, TransitionSnapshot, PendingWorkSnapshot

__all__ = [
    "Dispatcher",
    "AgentRegistry", 
    "WorkflowEngine",
    "TransitionRecord",
    "TransitionResult",
    "TaskStateManager",
    "TransitionSnapshot",
    "PendingWorkSnapshot",
]
