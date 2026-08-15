"""
Execution Strategy — Selector (Auto vs Manual Resolution).

Phase A deliverable 6 of TASK_DS_EO_043.
Source of truth: CTO_PLAN.md §5.5.

Singleton that resolves which execution strategy to use, with priority:
1. User override (persisted config or skill command)
2. Auto-detection via CapabilityAssessor

Persistence: overrides are stored in a sidecar JSON file so they survive
process restarts without requiring modification of the OpenClaw agent config.
"""

import json
import logging
import os
from threading import Lock
from typing import Optional, Tuple

from .constants import (
    Strategy,
    SELECTION_SOURCE_AUTO,
    SELECTION_SOURCE_USER_OVERRIDE,
)
from .capability_assessor import CapabilityAssessor
from .strategy_base import ExecutionStrategy, StrategyResult, CapabilityReport
# Phase B strategies imported lazily — they may not exist yet

logger = logging.getLogger(__name__)


# Where we persist user overrides. Created lazily on first override.
DEFAULT_OVERRIDE_PATH = os.path.join(
    "docs", "development", "reports", "TASK_DS_EO_043_MODEL_LIFECYCLE_MANAGER",
    "STRATEGY_OVERRIDE.json"
)


class ExecutionStrategySelector:
    """
    Resolves which execution strategy to use.

    Singleton per DS-EO process lifetime. Thread-safe for concurrent access.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, workspace_root=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
                    # Store workspace_root for __init__ to use
                    cls._instance._pending_workspace_root = workspace_root
        return cls._instance

    def __init__(self, workspace_root: str = None):
        """Initialize the selector. Safe to call multiple times — idempotent."""
        if self._initialized:
            return
        
        # Use pending workspace_root from __new__ if not passed again
        if workspace_root is None and hasattr(self, '_pending_workspace_root'):
            workspace_root = self._pending_workspace_root

        # Resolve workspace root
        if workspace_root is None:
            workspace_root = os.environ.get("DS_EO_WORKSPACE", os.getcwd())
        self.workspace_root = os.path.abspath(workspace_root)

        # Override persistence path (relative to workspace or absolute)
        override_path = os.environ.get(
            "DS_EO_STRATEGY_OVERRIDE_PATH",
            os.path.join(self.workspace_root, DEFAULT_OVERRIDE_PATH.lstrip("/")),
        )
        self._override_path = override_path

        # Strategy map: name → instance (lazy-loaded to avoid import errors for Phase B stubs)
        self._strategy_map: dict[str, object] = {}
        self._strategy_classes = {
            Strategy.CONCURRENT.value: "ConcurrentStrategy",
            Strategy.SEQUENTIAL.value: "SequentialStrategy",
            Strategy.SHARED_MODEL.value: "SharedModelStrategy",
        }

        # Current selection state (None = not yet resolved)
        self._selected_strategy_name: Optional[str] = None
        self._selection_source: Optional[str] = None
        self._initialized = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _get_or_create_strategy(self, name: str):
        """Lazy-load a strategy instance if not already cached."""
        if name in self._strategy_map:
            return self._strategy_map[name]

        class_name = self._strategy_classes.get(name)
        if not class_name or not _class_exists(class_name):
            logger.warning(
                f"Strategy '{name}' ({class_name}) is not yet implemented. "
                f"Returning a stub that will raise NotImplementedError at runtime."
            )
            # Create a stub instance
            from .strategy_base import ExecutionStrategy
            stub = _PhaseBStub(name, self.workspace_root)
            self._strategy_map[name] = stub
            return stub

        # Import and instantiate
        module_name = class_name.lower().replace("strategy", "_strategy") if "Strategy" in class_name else class_name.lower()
        try:
            mod = __import__(f".{module_name}", fromlist=[class_name])
            cls = getattr(mod, class_name)
            instance = cls(workspace_root=self.workspace_root) if hasattr(cls, '__init__') and 'workspace_root' in cls.__init__.__code__.co_varnames else cls()
            self._strategy_map[name] = instance
            return instance
        except Exception as e:
            logger.error(f"Failed to instantiate strategy '{name}': {e}")
            stub = _PhaseBStub(name, self.workspace_root)
            self._strategy_map[name] = stub
            return stub

    def get_or_resolve(self) -> Tuple[str, object, CapabilityReport]:
        """
        Get the current strategy. Resolve lazily if not yet selected.

        Returns:
            (strategy_name, strategy_instance, capability_report)
        """
        if self._selected_strategy_name is None:
            self._resolve()

        name = self._selected_strategy_name
        impl = self._get_or_create_strategy(name)

        report = CapabilityReport(
            strategy=name,
            confidence=0.9 if self._selection_source == SELECTION_SOURCE_AUTO else 1.0,
            signals={},
            reason=(
                f"User override: {name}"
                if self._selection_source == SELECTION_SOURCE_USER_OVERRIDE
                else "Auto-selected by capability assessment"
            ),
        )

        return (name, impl, report)

    def set_manual_override(self, strategy_name: str):
        """
        Persist a manual override and apply it immediately.

        Args:
            strategy_name: One of "concurrent", "sequential", "shared_model".

        Raises:
            ValueError: If the strategy name is not valid.
        """
        if strategy_name not in self._strategy_classes:
            raise ValueError(
                f"Unknown strategy: {strategy_name}. Valid options: "
                f"{list(self._strategy_classes.keys())}"
            )

        # Validate that the target strategy actually exists as a class
        if strategy_name == Strategy.SEQUENTIAL.value and not _class_exists("SequentialStrategy"):
            logger.warning(
                f"Manual override to '{strategy_name}' requested, but SequentialStrategy "
                f"is not yet implemented (Phase B). Proceeding anyway — will fail at runtime."
            )

        if strategy_name == Strategy.SHARED_MODEL.value and not _class_exists("SharedModelStrategy"):
            logger.warning(
                f"Manual override to '{strategy_name}' requested, but SharedModelStrategy "
                f"is not yet implemented (Phase B). Proceeding anyway — will fail at runtime."
            )

        self._selected_strategy_name = strategy_name
        self._selection_source = SELECTION_SOURCE_USER_OVERRIDE
        self._persist_override(strategy_name)
        logger.info(f"Manual override set to '{strategy_name}' by user")

    def clear_override(self):
        """Remove manual override and revert to auto-detection."""
        self._clear_persisted_override()
        self._resolve()  # re-run auto-detection
        logger.info("Manual override cleared; reverted to auto-selection")

    @property
    def current_strategy_name(self) -> str:
        """Return the currently selected strategy name (resolves if needed)."""
        if self._selected_strategy_name is None:
            self._resolve()
        return self._selected_strategy_name or Strategy.SEQUENTIAL.value  # safe default

    @property
    def selection_source(self) -> str:
        """Return the source tag ('auto' or 'user_override')."""
        if self._selected_strategy_name is None:
            self._resolve()
        return self._selection_source or SELECTION_SOURCE_AUTO

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve(self):
        """Run auto-detection and select strategy."""
        report = CapabilityAssessor.assess(workspace_root=self.workspace_root)

        # Check if the auto-selected strategy is a Phase B placeholder that can't run
        selected = report.strategy
        if (selected == Strategy.SEQUENTIAL.value and not _class_exists("SequentialStrategy")) or \
           (selected == Strategy.SHARED_MODEL.value and not _class_exists("SharedModelStrategy")):
            logger.warning(
                f"Auto-detection selected '{selected}' but its implementation is not yet available. "
                f"Falling back to concurrent."
            )
            selected = Strategy.CONCURRENT.value

        self._selected_strategy_name = selected
        self._selection_source = SELECTION_SOURCE_AUTO
        logger.info(f"Auto-selected strategy: {selected} (confidence={report.confidence})")

    def _persist_override(self, strategy_name: str):
        """Write override to sidecar JSON file."""
        override_data = {
            "strategy": strategy_name,
            "source": SELECTION_SOURCE_USER_OVERRIDE,
            "persisted_at": _now_iso(),
            "workspace_root": self.workspace_root,
        }

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(self._override_path) or ".", exist_ok=True)

        with open(self._override_path, "w") as f:
            json.dump(override_data, f, indent=2)

        logger.debug(f"Persisted strategy override to {self._override_path}")

    def _clear_persisted_override(self):
        """Remove the persisted override file if it exists."""
        if os.path.exists(self._override_path):
            try:
                os.remove(self._override_path)
                logger.debug(f"Cleared persisted override at {self._override_path}")
            except OSError as e:
                logger.warning(f"Failed to remove override file: {e}")

    # ------------------------------------------------------------------
    # Class-level convenience for checking Phase B availability
    # ------------------------------------------------------------------

    @classmethod
    def strategy_available(cls, name: str) -> bool:
        """Check if a strategy implementation exists (Phase A vs B)."""
        return _class_exists(name)


def _class_exists(class_name: str) -> bool:
    """Check if a class can be imported from the execution_strategy package."""
    import re
    import importlib
    
    # Derive module name: ConcurrentStrategy → concurrent_strategy, etc.
    snake = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()
    
    candidates = []
    if snake.endswith('strategy'):
        candidates.append(snake)
    else:
        candidates.append(f"{snake}_strategy")
    candidates.append(snake)
    
    for variant in candidates:
        try:
            mod = importlib.import_module(f".{variant}", package="dispatcher.execution_strategy")
            if hasattr(mod, class_name):
                return True
        except (ImportError, ModuleNotFoundError):
            continue
    return False


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class _PhaseBStub(ExecutionStrategy):
    """
    Stub for strategies not yet implemented (Phase B).
    
    Allows the selector to resolve to any strategy name without crashing,
    but raises NotImplementedError when actually used.
    """

    def __init__(self, strategy_name: str, workspace_root: str = None):
        self._strategy_name = strategy_name
        self.workspace_root = workspace_root

    async def prepare_for_agent(self, agent_id: str) -> StrategyResult:
        raise NotImplementedError(
            f"{self._strategy_name} strategy is not yet implemented (Phase B). "
            f"Use 'concurrent' mode or wait for Phase B completion."
        )

    async def release_agent(self, agent_id: str) -> StrategyResult:
        raise NotImplementedError(
            f"{self._strategy_name} strategy is not yet implemented (Phase B). "
            f"Use 'concurrent' mode or wait for Phase B completion."
        )

    def can_support_concurrent_agents(self) -> bool:
        return False  # Conservative default for unimplemented strategies

    def assess_capability(self) -> CapabilityReport:
        return CapabilityReport(
            strategy=self._strategy_name,
            confidence=0.0,
            signals={},
            reason=f"{self._strategy_name} not yet implemented (Phase B)",
        )
