"""DS-EO Runtime API — Abstraction boundary between DS-EO core and runtime harnesses.

RuntimeAPI is a typing.Protocol that defines the interface all runtime adapters must implement.
This module contains:
  - Data types: RuntimeModel, RuntimeSession, ActionResult
  - Protocol: RuntimeAPI (all 10 methods)
  - Factory: RuntimeAdapterFactory (resolve adapter by config)

Architecture Rule (AGENTS.md R-SI-2): DS-EO core modules import ONLY this interface.
Never import concrete implementations (DshRuntimeAdapter, OpenClawRuntimeAdapter).
"""

from __future__ import annotations
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

if sys.version_info >= (3, 10):
    from typing import Protocol
else:
    from typing_extensions import Protocol


# --------------------------------------------------------------------------- #
# Data Types — exchanged between DS-EO core and adapters
# --------------------------------------------------------------------------- #

@dataclass
class RuntimeModel:
    """Runtime-agnostic model description.

    Replaces hardcoded ollama/* model references (Dependency A5) with
    a provider-neutral model metadata type that any runtime can populate.
    """
    id: str                   # e.g., "ollama/qwen3.6:35b" or "dsh://model/xyz"
    context_window: int       # in tokens (must match ollama show | grep 'context length')
    max_tokens: int           # output token budget
    gpu_layers: int           # 0 = CPU only; -1 = all layers to GPU
    ram_bytes: int            # estimated RAM footprint on target hardware
    provider: str             # runtime identifier ("ollama", "dsh", etc.)
    params: dict = field(default_factory=dict)

@dataclass
class RuntimeSession:
    """Runtime-agnostic session representation.

    Replaces discovery of sessions via direct OpenClawAPI calls (Dependency A3).
    All adapters must populate this from their respective session stores.
    """
    key: str                   # unique session identifier
    agent_id: Optional[str]    # role name (cto, implementer, reviewer, pm)
    status: str                # "running" | "completed" | "error" | "idle"
    context_size_bytes: int = 0
    turn_count: int = 0
    last_turn_time: Optional[str] = None

@dataclass
class ActionResult:
    """Structured result from any runtime operation.

    Standardizes return types across adapters — replaces heterogeneous dict returns.
    """
    success: bool
    error: Optional[str] = None
    details: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# RuntimeAPI Protocol — the abstraction boundary (10 methods)
# --------------------------------------------------------------------------- #

class RuntimeAPI(Protocol):
    """
    The abstraction boundary between DS-EO core and the runtime harness.

    IMPLEMENTATION RULES (AGENTS.md Rule 9):
    - Each adapter implements this protocol independently.
    - DS-EO core code imports ONLY this Protocol type — never concrete implementations.
    - When a method has no meaningful implementation in a given runtime,
      raise NotImplementedError with a TODO comment explaining the DSH/runtime-specific target.

    Methods map to OpenClaw dependencies A1–A11:
      - compact_session  → A1 (compaction)
      - archive_session  → A1 (archive/trajectory bundle)
      - close_session    → A1 (close session)
      - get_session_info → A3 (session discovery)
      - spawn_session    → A6 (sessions_spawn equivalent)
      - submit_task      → A6 (task dispatch)
      - run_tools        → A8 (tool policy gate)
      - model_info       → A5, A9 (model metadata)
      - available_models → A5, A9 (model list)
      - run_task         → A2 (generic tool execution)
      - register_binding → A7 (slash-command / hook bindings)
    """

    # === Session lifecycle (A1) ===
    def compact_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        """Compact a stored session transcript. Returns success or error with details."""
        ...

    def archive_session(self, session_key: str, agent_id: Optional[str] = None,
                        dest_dir: Optional[str] = None) -> ActionResult:
        """Export a trajectory bundle for archival at optional dest_dir (runtime-agnostic path)."""
        ...

    def close_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        """Close/remove a stored session. May return partial success if not supported."""
        ...

    def get_session_info(self, session_key: str, agent_id: Optional[str] = None) -> Optional[RuntimeSession]:
        """Get information about a specific stored session. Returns None if not found."""
        ...

    # === Session spawning and task dispatch (A6) ===
    def spawn_session(self, config: dict) -> ActionResult:
        """
        Spawn a new agent session with configuration.

        Args:
            config: {
                "agent_id": str,           # role name (cto/implementer/reviewer/pm)
                "model": str,              # provider-agnostic model identifier
                "workspace_root": str,     # project directory path
                "task_id": Optional[str],  # TASK_DS_EO_XXX identifier
                "plan": Optional[dict],    # task plan dict
                "tool_policy": dict,       # {allow: [...], deny: [...]}
            }

        Returns:
            ActionResult with session.key in details["session_key"] on success.
        """
        ...

    def submit_task(self, task: dict, role: str, plan: Optional[dict] = None) -> ActionResult:
        """Submit a task for execution within an agent session."""
        ...

    def run_tools(self, session_key: str, tool_name: str, tool_args: dict,
                  policy: Optional[dict] = None) -> ActionResult:
        """Execute a tool within a session with optional policy gate.

        Faithfully replicates OpenClaw gateway.tools.allow semantics:
        - If policy is provided, check tool_name against allow/deny lists
        - Return success=True + result if allowed, or success=False + error if denied
        - If no policy, use runtime default behavior
        """
        ...

    # === Model registry (A5, A9) ===
    def model_info(self, model_id: str) -> RuntimeModel:
        """Get runtime-agnostic model metadata. Returns full RuntimeModel with all fields."""
        ...

    def available_models(self) -> list[RuntimeModel]:
        """List all candidate models available from the runtime."""
        ...

    # === Generic tool execution (A2, A8) ===
    def run_task(self, tool: str, args: dict) -> ActionResult:
        """Generic tool execution harness — replaces direct subprocess.run in release_manager.py.

        Used for non-session-specific tool invocations (e.g., deployment scripts,
        config validation, etc.).
        """
        ...

    # === Hooks and bindings (A7) ===
    def register_binding(self, command: str, handler_fn: Any) -> bool:
        """Register a command-to-handler binding (slash commands or DSH hooks).

        Returns True if registration succeeded, False otherwise.
        The same method name is used for both OpenClaw slash bindings and DSH hooks
        to maintain interface consistency across runtimes.
        """
        ...


# --------------------------------------------------------------------------- #
# Factory — resolve active adapter from configuration
# --------------------------------------------------------------------------- #

class RuntimeAdapterFactory:
    """Factory to resolve the active runtime adapter from configuration.

    Usage:
        adapter = RuntimeAdapterFactory.create(runtime="dsh")      # explicit
        adapter = RuntimeAdapterFactory.create(runtime="auto")     # checks manifest
        adapter = RuntimeAdapterFactory.create()                   # defaults to "openclaw"
    """

    @staticmethod
    def create(runtime: str = "auto") -> RuntimeAPI:
        """Create a RuntimeAPI instance for the specified runtime.

        Args:
            runtime: "dsh" | "openclaw" | "auto".
                     "auto" checks ds_eo_manifest.yaml → dsh_default_runtime config.
                     Default is "dsh".

        Returns:
            RuntimeAPI instance — either DshRuntimeAdapter or OpenClawRuntimeAdapter.

        Raises:
            ValueError if runtime is unknown.
        """
        # Lazy imports to avoid circular dependencies at module load time
        if runtime == "auto":
            try:
                from ..manifest_loader import get_default_runtime
                runtime = get_default_runtime() or "dsh"
            except ImportError:
                # manifest_loader may not exist yet in early Phase 0 — use default
                runtime = "openclaw"

        if runtime == "dsh":
            from .dsh_adapter import DshRuntimeAdapter
            # Verify DSH API is accessible before returning this adapter
            if not os.environ.get("DSH_API_BASE"):
                raise RuntimeError(
                    "DshRuntimeAdapter selected but DSH_API_BASE is not set. "
                    "Set the DSH_API_BASE environment variable to your DSH endpoint URL, "
                    "or configure runtime='openclaw' for OpenClaw fallback."
                )
            return DshRuntimeAdapter()
        elif runtime == "openclaw":
            from .openclaw_bridge import OpenClawRuntimeAdapter
            return OpenClawRuntimeAdapter()
        else:
            raise ValueError(f"Unknown runtime '{runtime}'. Must be 'dsh', 'openclaw', or 'auto'.")
