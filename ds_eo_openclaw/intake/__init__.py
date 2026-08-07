"""
DS-EO Task Intake — public API.

Provides TaskIntakeManager for PM-driven task intake and workspace initialization.
"""

from .task_intake import TaskIntakeManager, create_task_intake

__all__ = ["TaskIntakeManager", "create_task_intake"]
