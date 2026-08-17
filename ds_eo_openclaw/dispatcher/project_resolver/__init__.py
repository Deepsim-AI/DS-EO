"""DS-EO Multi-Project Architecture — Project Resolver package."""

from .resolver import (
    ProjectResolver,
    ProjectManifestLoader,
    ProjectInfo,
    AgentIdentityMatrix,
    AgentIdentity,
    DEFAULT_CATALOG_PATH,
    resolve_project_for_task,
)
from .task_id_manager import TaskIDManager, TaskIDInfo, TASK_ID_PATTERN

__all__ = [
    "ProjectResolver",
    "ProjectManifestLoader",
    "ProjectInfo",
    "AgentIdentityMatrix",
    "AgentIdentity",
    "DEFAULT_CATALOG_PATH",
    "TaskIDManager",
    "TaskIDInfo",
    "TASK_ID_PATTERN",
    "resolve_project_for_task",
]
