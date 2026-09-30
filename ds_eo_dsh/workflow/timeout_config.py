"""Per-state timeout configuration for stall detection.

Implements §9.3 of EXECUTION_MODE_ARCHITECTURE.md — configurable timeouts
per workflow state with human-ownership exemptions. Human-owned states
(G1_WAITING, G3_PENDING, FINAL_APPROVAL) are exempt from stall detection
regardless of elapsed time.

Usage:
    config = TimeoutConfig()  # uses defaults
    config = TimeoutConfig(overrides={"IMPLEMENTATION": 7200})  # custom override
    is_exempt = config.is_exempt("G1_WAITING")  # → True (human-owned)
"""

from datetime import datetime, timezone


class TimeoutConfig:
    """Per-state timeout configuration with human-ownership exemptions.

    Attributes:
        timeouts: Dict mapping state name to timeout in seconds.
            None = exempt from stall detection (human-owned states).

    Human-owned states (always exempt):
        G1_WAITING — User reviews CTO plan
        G3_PENDING — Reviewer evaluates review report
        FINAL_APPROVAL — CTO makes final decision at Gate G4

    Non-exempt states have configurable timeouts with sensible defaults.
    """

    # Default timeouts per state (§9.3 of architecture)
    DEFAULTS: dict[str, int | None] = {
        "TASK_OPEN":      86400,   # 24h — user takes time to review plans
        "G1_WAITING":     None,    # Human-owned, exempt from stall detection
        "IMPLEMENTATION": 36000,   # 10h — reasonable coding window
        "WAITING_G2":      3600,   # 1h — implementer writes report
        "REVIEW":         7200,    # 2h — review window
        "G3_PENDING":     None,    # Human-owned (CTO evaluation), exempt
        "FINAL_APPROVAL": None,    # Human-owned (CTO decision), exempt
        "COMPLETED":      None,    # Terminal state
        "CHANGES_REQD":   7200,    # 2h — rework submission window
        "BLOCKED":        1800,    # 30min — blockers should be resolved fast
        "STALLED":        None,    # Already stalled (terminal)
    }

    def __init__(self, overrides: dict[str, int | None] | None = None):
        """Initialize timeout config with defaults and optional overrides.

        Args:
            overrides: Dict of state→timeout to override defaults. Unknown states
                raise ValueError. None values mark states as exempt (human-owned).

        Raises:
            ValueError: If any key in overrides is not a valid state name.
        """
        self.timeouts: dict[str, int | None] = dict(self.DEFAULTS)
        if overrides:
            for state, timeout in overrides.items():
                if state not in self.DEFAULTS and state != "enabled":
                    raise ValueError(
                        f"Unknown state '{state}' in timeout overrides. "
                        f"Valid states: {list(self.DEFAULTS.keys())}"
                    )
                self.timeouts[state] = timeout

    def is_exempt(self, state: str) -> bool:
        """Check if a state is exempt from stall detection (human-owned).

        Human-ownership states (§6.1 of architecture) are never subject to
        automated stall detection regardless of elapsed time. This ensures
        human reviewers and decision-makers aren't penalized for taking time.

        Args:
            state: State name to check.

        Returns:
            True if the state is exempt (None timeout), False otherwise.
        """
        return self.timeouts.get(state) is None

    def get_timeout(self, state: str) -> int | None:
        """Get the configured timeout for a state in seconds.

        Args:
            state: State name to look up.

        Returns:
            Timeout in seconds (int), or None if state is exempt.
        """
        return self.timeouts.get(state)

    def validate_state(self, state: str) -> bool:
        """Check if a state name is recognized by this config.

        Args:
            state: State name to validate.

        Returns:
            True if the state exists in the configuration.
        """
        return state in self.timeouts

    def set_timeout(self, state: str, timeout: int | None) -> None:
        """Set or update a per-state timeout.

        Args:
            state: State name to configure.
            timeout: Timeout in seconds (None = exempt from stall detection).

        Raises:
            ValueError: If state is not recognized.
        """
        if state not in self.DEFAULTS and state != "enabled":
            raise ValueError(
                f"Unknown state '{state}'. Valid states: {list(self.DEFAULTS.keys())}"
            )
        self.timeouts[state] = timeout

    def exempt_states(self) -> list[str]:
        """Return all states that are exempt from stall detection.

        Returns:
            List of state names with None timeout (human-owned).
        """
        return [s for s, t in self.DEFAULTS.items() if t is None]

    def active_states(self) -> dict[str, int]:
        """Return all non-exempt states with their configured timeouts.

        Returns:
            Dict of state→timeout (int seconds only).
        """
        return {s: t for s, t in self.DEFAULTS.items() if t is not None}


# --------------------------------------------------------------------------- #
# Default config instance
# --------------------------------------------------------------------------- #

DEFAULT_TIMEOUT_CONFIG = TimeoutConfig()
"""Global default timeout configuration — uses architecture §9.3 defaults."""
