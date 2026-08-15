"""
Execution Strategy — Abstract Base Class Contract.

Phase A deliverable 3 of TASK_DS_EO_043.
Source of truth: CTO_PLAN.md §5.1 — verbatim interface definition.

This is the non-negotiable contract that all three strategy implementations
(concurrent, sequential, shared_model) must satisfy.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# ============================================================================
# Data Classes (verbatim from CTO_PLAN.md §5.1)
# ============================================================================

@dataclass
class StrategyResult:
    """Result of a strategy prepare/release operation."""
    success: bool
    strategy: str  # "concurrent" | "sequential" | "shared_model"
    model_status: dict  # {model_name: {"installed": bool, "loaded": bool, "executing": bool}}
    notes: list = field(default_factory=list)

    # Optional metadata attached by ExecutionStrategyManager
    metadata: Optional[dict] = None


@dataclass
class CapabilityReport:
    """Output of capability assessment for auto-selection."""
    strategy: str  # recommended strategy name
    confidence: float  # 0.0 - 1.0
    signals: dict  # raw signal values used for decision
    reason: str  # human-readable explanation


# ============================================================================
# Abstract Base Class (verbatim from CTO_PLAN.md §5.1)
# ============================================================================

class ExecutionStrategy(ABC):
    """Common interface for all execution strategies."""

    @abstractmethod
    async def prepare_for_agent(self, agent_id: str) -> StrategyResult:
        """
        Ensure the target model/environment is ready for an agent.

        Returns StrategyResult with:
            - success: bool
            - strategy: str (strategy name)
            - model_status: dict describing current model state
            - notes: list of human-readable status messages

        Raises StrategyError with typed codes.
        """

    @abstractmethod
    async def release_agent(self, agent_id: str) -> StrategyResult:
        """Clean up after an agent phase completes."""

    @abstractmethod
    def can_support_concurrent_agents(self) -> bool:
        """Return True if this strategy supports concurrent spawning."""

    @abstractmethod
    def assess_capability(self) -> CapabilityReport:
        """For auto-selection: return hardware capability report."""
