# Phase 1 - ExecutionHandle + runtime-neutral RuntimeAPI.
"""Runtime-neutral execution abstraction for DS-EO.

This defines the neutral RuntimeAPI and ExecutionHandle.

DS-EO NEVER treats OpenClaw's persistent ``session`` as a first-class
concept.  An execution is a neutral handle with execution_id, runtime,
native_id, status and metadata.  Concrete backends (DSH, OpenClaw)
implement RuntimeAPI.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = [
    "RuntimeKind", "ExecutionStatus", "LifecycleStage",
    "ExecutionHandle", "RuntimeAPI", "RuntimeError",
]


class RuntimeError(Exception):
    """Adapter failure sentinel, distinct from built-in RuntimeError."""


class RuntimeKind:
    """Runtime backend identifiers."""

    DSH = "dsh"
    OPENCLAW = "openclaw"


class ExecutionStatus:
    """Neutral execution lifecycle stages."""

    CREATED = "created"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    ERROR = "error"


class LifecycleStage(ExecutionStatus):
    """Alias so callers can read .status or lifecycle consistently."""


def now_ms() -> int:
    """Current time in epoch milliseconds."""
    return int(time.time() * 1000)


@dataclass
class ExecutionHandle:
    """Runtime-neutral description of one execution.

    Exactly: execution_id, runtime, native_id, status, metadata.
    """

    execution_id: str
    runtime: str
    native_id: str
    status: str = ExecutionStatus.CREATED
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_terminal(self) -> bool:
        return self.status in frozenset({
            ExecutionStatus.DONE, ExecutionStatus.CANCELLED,
            ExecutionStatus.ERROR,
        })

    def copy_with(self, **overrides):
        """Return a new handle with the given fields overridden."""
        return ExecutionHandle(
            execution_id=overrides.get("execution_id", self.execution_id),
            runtime=overrides.get("runtime", self.runtime),
            native_id=overrides.get("native_id", self.native_id),
            status=overrides.get("status", self.status),
            metadata=dict(self.metadata, **(overrides.get("metadata") or {})),
        )

    def to_dict(self):
        return {
            "execution_id": self.execution_id,
            "runtime": self.runtime,
            "native_id": self.native_id,
            "status": self.status,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data):
        """Build a handle from a dict (serialization / fixtures)."""
        return cls(
            execution_id=data["execution_id"],
            runtime=data["runtime"],
            native_id=data.get("native_id", ""),
            status=data.get("status", ExecutionStatus.CREATED),
            metadata=dict(data.get("metadata") or {}),
        )


class RuntimeAPI(abc.ABC):
    """Abstract runtime-neutral execution contract (Phase 1 boundary).

    Every method speaks in stable execution_ids plus neutral lifecycle
    operations (execute, submit, status, cancel, recover, logs, artifacts).
    The DSH adapter and a thin OpenClaw adapter both implement this.
    """

    @abc.abstractmethod
    def execute(self, command, *, timeout: int = 120):
        """Run a job to completion. Returns DONE (rc 0) or ERROR handle."""
        raise NotImplementedError

    @abc.abstractmethod
    def submit(
        self, task_id: str, execution_id: Optional[str] = None,
        *, prompt: str = "", tool: Optional[str] = None,
        args: Optional[dict] = None, model: Optional[str] = None,
        role: Optional[str] = None, metadata: Optional[dict] = None,
    ) -> ExecutionHandle:
        """Create a RUNNING handle bound to a task_id. Never raises."""
        raise NotImplementedError

    @abc.abstractmethod
    def status(self, execution_id: str) -> ExecutionHandle:
        """Return final state of an execution, never raising."""
        raise NotImplementedError

    @abc.abstractmethod
    def cancel(self, execution_id: str) -> ExecutionHandle:
        """Mark an in-flight execution cancelled. Never raises."""
        raise NotImplementedError

    @abc.abstractmethod
    def recover(self, execution_id: str, metadata: Optional[dict] = None) -> ExecutionHandle:
        """Resume a cancelled execution. Never raises."""
        raise NotImplementedError

    @abc.abstractmethod
    def logs(self, execution_id: str, limit: int = 200) -> list:
        """Recent log lines for an execution (maybe empty)."""
        raise NotImplementedError

    @abc.abstractmethod
    def artifacts(self, execution_id: str, limit: int = 200) -> list:
        """Recent artifact paths for an execution (maybe empty)."""
        raise NotImplementedError
