# DS-EO Session Health — Runtime abstraction (Phase 1).

"""Runtime-independent interface that DS-EO business logic depends on.

DS-EO session-health logic (discoverer, classifier, monitor, executor, audit)
must no longer depend on OpenClaw primitives directly. All such dependencies go
through the abstract runtime interface defined here. Concrete runtime bindings
implement :class:`RuntimeAPI`; see :mod:`.dsh_adapter` (primary) and
:mod:`.openclaw_bridge` (legacy).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


class RuntimeError(Exception):
    """Raised when a runtime adapter operation fails.

    Distinct from built-in :class:`RuntimeError` so DS-EO code can catch
    adapter failures specifically.
    """


class RuntimeSessionId(str):
    """Opaque session identifier returned by the runtime.

    Backed by a plain string so it interoperates with existing session-key
    strings, but typed separately to force callers to treat it as an opaque
    runtime token (never parsed for structure, never constructed by hand).
    """


class RuntimeModel:
    """A model the runtime could load. id is the key."""

    __slots__ = ("id",)

    def __init__(self, id: str) -> None:
        self.id = id


class ToolPolicy:
    """Tool execution policy. allow/deny are lists of tool names or groups."""

    __slots__ = ("allow", "deny")

    def __init__(self, allow: list[str] | None = None, deny: list[str] | None = None) -> None:
        self.allow = list(allow) if allow else None
        self.deny = list(deny) if deny else None

    @classmethod
    def allows(cls, policy: "ToolPolicy | None", tool: str) -> bool:
        """Whether ``tool`` may run under ``policy``.

        * ``policy is None`` -> allow everything.
        * empty allow and deny -> allow everything.
        * ``"write"`` in allow -> all write tools allowed (any non-denied tool).
        * otherwise -> ``tool`` must be in allow (and not in deny).
        """
        if not tool:
            return False
        if policy is None:
            return True
        allow = policy.allow or []
        deny = policy.deny or []
        if "write" in allow:
            return tool not in deny
        return tool in (allow or []) and tool not in deny


@dataclass
class ActionResult:
    """Result of a runtime action.

    ``action`` is a short human-readable label (e.g. "session-compact").
    """

    action: str
    success: bool = False
    success_detail: str | None = None
    context_after_kb: int | None = None
    context_before_kb: int | None = None
    tool_result: dict | None = None
    error: str | None = None

    @classmethod
    def ok(cls, action: str, **kw: Any) -> "ActionResult":
        return cls(action=action, success=True, **kw)

    @classmethod
    def failed(cls, action: str, message: str) -> "ActionResult":
        return cls(action=action, success=False, error=message)


@dataclass
class SessionInfo:
    """Runtime view of a single session; guaranteed by RuntimeAPI:

    ``runtime_session_id`` is always populated and never None.
    """

    runtime_session_id: RuntimeSessionId
    status: str = "unknown"
    tool_policy: ToolPolicy | None = None


@dataclass
class ToolResult:
    """Result of a tool call. ``ok`` is the only contract field."""

    ok: bool
    data: Any = None
    tool: str | None = None
    error_message: str | None = None


class RuntimeAPI(abc.ABC):
    """The abstract runtime interface DS-EO depends on."""

    # -- session lifecycle -------------------------------------------------
    @abc.abstractmethod
    def spawn_session(
        self, model: str | None, task_id: str, session_id: str
    ) -> RuntimeSessionId:
        """Return an opaque session handle. Never parse/construct its value."""

    @abc.abstractmethod
    def submit_task(
        self, session_id: RuntimeSessionId, task_id: str, message: str
    ) -> ActionResult:
        """Submit a task message to a live session."""

    @abc.abstractmethod
    def abort_session(self, session_id: RuntimeSessionId) -> ActionResult:
        """Abandon a live session (recoverable via re-spawn)."""

    @abc.abstractmethod
    def session_status(self, session_id: RuntimeSessionId) -> SessionInfo:
        """Return current session info; runtime_session_id always populated."""

    @abc.abstractmethod
    def compact_session(self, session_id: RuntimeSessionId) -> ActionResult:
        """Compact a live session's context window."""

    @abc.abstractmethod
    def archive_session(
        self, session_id: RuntimeSessionId, dest: str | None
    ) -> dict[str, Any]:
        """Persist a session transcript. Plain result dict."""

    @abc.abstractmethod
    def close_session(self, session_id: RuntimeSessionId) -> dict[str, Any]:
        """Close a finished session. Plain result dict."""

    # -- tools -------------------------------------------------------------
    @abc.abstractmethod
    def run_tool(
        self,
        tool: str,
        args: dict[str, Any],
        policy: ToolPolicy | None = None,
    ) -> ToolResult:
        """Run a tool under ``policy``. Must NEVER raise; return ok=False on error."""

    # -- models ------------------------------------------------------------
    @abc.abstractmethod
    def available_models(self) -> list[RuntimeModel]:
        """List models the runtime can load. Must not raise for none."""

    @abc.abstractmethod
    def model_info(self, model_id: str) -> RuntimeModel | None:
        """Return info for a model, or None if unknown. Must not raise for none."""
