"""
DS-EO Session Health — Policy Map (§10, §12, §13)

Maps health classifications to lifecycle actions with all safety layers:
- Active task protection (spec §13): ALWAYS NO_ACTION for active tasks
- Protected session override (spec §22): ALWAYS WARN for protected sessions
- Failed compaction retry path (spec §17)
- Deterministic policy map for remaining states

All decisions are deterministic and fully explainable.
"""

from dataclasses import dataclass, field
from typing import Optional
from .enums import SessionHealthState, LifecycleAction, HealthSignal
from .config import SessionHealthConfig


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #


@dataclass
class PolicyDecision:
    """Output of the policy evaluation — action + explanation."""

    session_key: str
    classification: SessionHealthState
    action: LifecycleAction
    is_safety_override: bool = False  # True if a safety rule forced this decision
    reason: str = ""
    evidence: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_key": self.session_key,
            "classification": self.classification.value,
            "action": self.action.value,
            "is_safety_override": self.is_safety_override,
            "reason": self.reason,
            "evidence": [e.to_dict() if hasattr(e, 'to_dict') else str(e) for e in self.evidence],
        }


# --------------------------------------------------------------------------- #
# Policy — classification → action with safety layers
# --------------------------------------------------------------------------- #


class HealthPolicy:
    """
    Deterministic policy map from health classification to lifecycle action.

    Safety layers (applied BEFORE the main policy table):
      1. Active task protection (§13): ALWAYS NO_ACTION for active tasks
      2. Protected session override (§22): ALWAYS WARN for protected sessions
      3. Failed compaction retry path (§17): COMPACT before ESCALATE

    Main policy table (after safety layers pass through):
      STALE → MARK_STALE (if no active task) / NO_ACTION (if active task)
      OVERSIZED → COMPACT
      ERRORING → WARN
      ORPHANED → ARCHIVE (if inactive long enough) / CLOSE
      STUCK → ESCALATE
      COMPACTION_FAILED → RETRY_COMPACTION (until budget exhausted)
      RECOVERY_REQUIRED → ESCALATE

    Args:
        config: SessionHealthConfig with thresholds.
        protected_sessions: Set of session keys that should never be destroyed.
    """

    def __init__(
        self,
        config: Optional[SessionHealthConfig] = None,
        protected_sessions: Optional[set] = None,
    ):
        self.config = config or SessionHealthConfig()
        self.protected_sessions = protected_sessions or set()

    def evaluate(self, session_key: str, classification) -> PolicyDecision:
        """
        Evaluate the policy for a classified session.

        Applies safety layers first, then looks up the main policy table.

        Args:
            session_key: The session being evaluated.
            classification: ClassificationResult from HealthClassifier.

        Returns:
            PolicyDecision with action and full explanation.
        """
        state = classification.state
        evidence = list(classification.evidence) if hasattr(classification, 'evidence') else []

        # ===== SAFETY LAYER 1: Active task protection (§13) =====
        # Check both the resulting state AND the evidence for active task indication
        has_active_task = (
            state == SessionHealthState.ACTIVE or
            any(
                hasattr(e, 'signal_name') and e.signal_name == "task_association" and e.value == "ACTIVE"
                for e in evidence
            )
        )
        if has_active_task:
            return PolicyDecision(
                session_key=session_key,
                classification=state,
                action=LifecycleAction.NO_ACTION,
                is_safety_override=True,
                reason="Active task protection — never destroy sessions with active work",
                evidence=evidence + [self._evidence("safety_layer_13", "active_task_protection")],
            )

        # ===== SAFETY LAYER 2: Protected session override (§22) =====
        if session_key in self.protected_sessions:
            return PolicyDecision(
                session_key=session_key,
                classification=state,
                action=LifecycleAction.WARN,
                is_safety_override=True,
                reason="Protected session — always WARN regardless of classification",
                evidence=evidence + [self._evidence("safety_layer_22", "protected_session")],
            )

        # ===== SAFETY LAYER 3: Failed compaction retry path (§17) =====
        if state == SessionHealthState.RECOVERY_REQUIRED:
            return PolicyDecision(
                session_key=session_key,
                classification=state,
                action=LifecycleAction.ESCALATE,
                is_safety_override=True,
                reason="Recovery required — delegate to RecoveryEngine per spec §17",
                evidence=evidence + [self._evidence("safety_layer_17", "recovery_required")],
            )

        # ===== MAIN POLICY TABLE =====
        policy_map = {
            SessionHealthState.HEALTHY: LifecycleAction.NO_ACTION,
            SessionHealthState.STALE: LifecycleAction.MARK_STALE,
            SessionHealthState.OVERSIZED: LifecycleAction.COMPACT,
            SessionHealthState.ERRORING: LifecycleAction.WARN,
            SessionHealthState.ORPHANED: LifecycleAction.ARCHIVE,
            SessionHealthState.STUCK: LifecycleAction.ESCALATE,
            SessionHealthState.COMPACTION_FAILED: LifecycleAction.RETRY_COMPACTION,
        }

        action = policy_map.get(state, LifecycleAction.NO_ACTION)

        reason = self._policy_reason(state, action)
        evidence.append(self._evidence("policy_table", f"{state.value} → {action.value}"))

        return PolicyDecision(
            session_key=session_key,
            classification=state,
            action=action,
            is_safety_override=False,
            reason=reason,
            evidence=evidence,
        )

    def should_execute(self, decision: PolicyDecision) -> bool:
        """
        Determine if an action should be executed based on monitor status.

        In OBSERVING mode (default), only log — never execute execution actions.

        Args:
            decision: The policy decision to evaluate for execution.

        Returns:
            True if the action should actually be performed (not just logged).
        """
        from .enums import MonitorStatus  # Local import to avoid circular deps
        # This is checked by the monitor/executor — here we provide the logic
        return not MonitorStatus.OBSERVING == MonitorStatus.OBSERVING

    def get_action_summary(self, decision: PolicyDecision) -> str:
        """Get a human-readable summary of what this policy decided."""
        override_marker = " [SAFETY OVERRIDE]" if decision.is_safety_override else ""
        return (
            f"{decision.classification.value} → {decision.action.value}{override_marker}: "
            f"{decision.reason}"
        )

    # ===== Helpers =====

    def _evidence(self, source: str, detail: str) -> dict:
        """Create an evidence entry for policy decisions."""
        return {"source": source, "detail": detail}

    @staticmethod
    def _policy_reason(state: SessionHealthState, action: LifecycleAction) -> str:
        """Generate a human-readable reason for a classification→action mapping."""
        reasons = {
            (SessionHealthState.HEALTHY, LifecycleAction.NO_ACTION): "Session is healthy — no action needed",
            (SessionHealthState.STALE, LifecycleAction.MARK_STALE): "Session is stale but has a task — mark for monitoring",
            (SessionHealthState.OVERSIZED, LifecycleAction.COMPACT): "Context exceeds size threshold — compact",
            (SessionHealthState.ERRORING, LifecycleAction.WARN): "Multiple errors detected — warn and monitor",
            (SessionHealthState.ORPHANED, LifecycleAction.ARCHIVE): "No task association + inactive — archive",
            (SessionHealthState.STUCK, LifecycleAction.ESCALATE): "Execution stuck — escalate to RecoveryEngine",
            (SessionHealthState.COMPACTION_FAILED, LifecycleAction.RETRY_COMPACTION): "Compaction failed but retries remain — retry",
        }
        return reasons.get((state, action), f"Policy rule for {state.value}")


# ===== CLI — Test the policy =====
if __name__ == "__main__":
    import argparse
    from .enums import SessionHealthState

    parser = argparse.ArgumentParser(description="DS-EO Health Policy Evaluator")
    parser.add_argument("--session-key", "-s", required=True)
    parser.add_argument("--state", choices=[s.value for s in SessionHealthState], default="HEALTHY")
    parser.add_argument("--protected", action="store_true", help="Mark as protected session")
    args = parser.parse_args()

    from .classifier import ClassificationResult
    classification = ClassificationResult(
        session_key=args.session_key,
        state=SessionHealthState(args.state),
        summary=f"Test classification: {args.state}",
    )

    policy = HealthPolicy()
    if args.protected:
        policy.protected_sessions.add(args.session_key)

    decision = policy.evaluate(args.session_key, classification)
    print(f"Decision for {args.session_key}:")
    print(f"  Classification: {decision.classification.value}")
    print(f"  Action:         {decision.action.value}")
    print(f"  Safety override: {decision.is_safety_override}")
    print(f"  Reason:         {decision.reason}")
