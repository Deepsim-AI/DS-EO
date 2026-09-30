"""
DS-EO Session Health — Health Classifier (§8, §9)

Deterministic classification with explainability. Maps multi-signal inputs
from the Discoverer to a single health classification using configurable
thresholds from config.py. Every result includes human-readable explanation
of which signals triggered what decision.

Architecture Decision (CTO Plan §1.3): Classifier is pure — no side effects,
no disk I/O. Receives SessionHealthData + Config, returns ClassificationResult.
"""

from dataclasses import dataclass, field
from typing import Optional
from .enums import SessionHealthState, HealthSignal
from .config import SessionHealthConfig


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #


@dataclass
class SignalEvidence:
    """Why a particular classification was chosen."""
    signal_name: str
    value: object
    threshold: Optional[str] = None
    conclusion: str = ""

    def to_dict(self) -> dict:
        return {
            "signal": self.signal_name,
            "value": self.value,
            "threshold": self.threshold,
            "conclusion": self.conclusion,
        }


@dataclass
class ClassificationResult:
    """Output of the classifier — deterministic classification + explanation."""

    session_key: str
    state: SessionHealthState
    confidence: float = 1.0  # Always 1.0 for deterministic rules; reserved for future ML

    # Human-readable explanation chain
    evidence: list = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "session_key": self.session_key,
            "state": self.state.value,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "summary": self.summary,
        }


# --------------------------------------------------------------------------- #
# Classifier — deterministic multi-signal → classification
# --------------------------------------------------------------------------- #


class HealthClassifier:
    """
    Deterministic health classifier.

    Applies a fixed priority rule set to SessionHealthData from the Discoverer,
    producing ClassificationResult with full explainability. The priority order
    ensures safety-critical states (RECOVERY_REQUIRED) override less critical ones.

    Priority order (highest to lowest):
      1. Active task protection → ACTIVE
      2. Compaction failed + retry exhausted → RECOVERY_REQUIRED
      3. Compaction failed but retries remain → COMPACTION_FAILED
      4. Context exceeds oversized threshold → OVERSIZED
      5. Errors exceed error_threshold → ERRORING
      6. Orphaned (no task, inactive) → ORPHANED
      7. Inactive beyond stale threshold → STALE
      8. Execution stuck → STUCK
      9. Default: HEALTHY

    Args:
        config: SessionHealthConfig with all thresholds.
    """

    def __init__(self, config: Optional[SessionHealthConfig] = None):
        self.config = config or SessionHealthConfig()

    def classify(self, data) -> ClassificationResult:
        """
        Classify a session's health state from discovered signals.

        Args:
            data: SessionHealthData from the Discoverer.

        Returns:
            ClassificationResult with state and full explanation chain.
        """
        evidence = []
        summary_parts = []

        # Rule 1: Active task protection — never classify as unhealthy if actively working
        if self._is_active_task(data):
            result = ClassificationResult(
                session_key=data.session_key,
                state=SessionHealthState.ACTIVE,
                confidence=1.0,
                evidence=evidence + [
                    SignalEvidence(
                        signal_name="task_association",
                        value=data.task_association,
                        conclusion="Active task detected — protecting from unhealthy classification",
                    )
                ],
                summary=f"Session has active task ({data.task_association}); classified ACTIVE for protection",
            )
            return result

        # Rule 2: Compaction failed + retry exhausted → RECOVERY_REQUIRED
        if data.compaction_status == "FAILED":
            recovery_attempts = len(data.recovery_history) or 0
            max_retries = self.config.max_compaction_attempts
            evidence.append(SignalEvidence(
                signal_name="compaction_status",
                value=data.compaction_status,
                threshold=f"max_attempts={max_retries}",
                conclusion="Compaction failed",
            ))

            if recovery_attempts > max_retries:
                result = ClassificationResult(
                    session_key=data.session_key,
                    state=SessionHealthState.RECOVERY_REQUIRED,
                    evidence=evidence + [SignalEvidence(
                        signal_name="recovery_history_count",
                        value=recovery_attempts,
                        threshold=f">{max_retries}",
                        conclusion="Retry budget exhausted — recovery required",
                    )],
                    summary=(
                        f"Compaction failed with {recovery_attempts}/{max_retries} retries used; "
                        f"RECOVERY_REQUIRED"
                    ),
                )
                return result
            else:
                evidence.append(SignalEvidence(
                    signal_name="recovery_history_count",
                    value=recovery_attempts,
                    threshold=f"<{max_retries}",
                    conclusion="Retries remain — not yet RECOVERY_REQUIRED",
                ))

        # Rule 3: Compaction required (successful but flagged)
        if data.compaction_status == "OK" and self._context_is_oversized(data):
            evidence.append(SignalEvidence(
                signal_name="context_size_kb",
                value=data.context_size_kb,
                threshold=f">{self.config.oversized_context_kb}",
                conclusion="Context exceeds oversized threshold",
            ))
            result = ClassificationResult(
                session_key=data.session_key,
                state=SessionHealthState.OVERSIZED,
                evidence=evidence,
                summary=(
                    f"Context size {data.context_size_kb}KB exceeds "
                    f"{self.config.oversized_context_kb}KB threshold; OVERSIZED"
                ),
            )
            return result

        # Rule 4: Errors exceed threshold
        if data.error_count >= self.config.error_threshold:
            evidence.append(SignalEvidence(
                signal_name="error_count",
                value=data.error_count,
                threshold=f">={self.config.error_threshold}",
                conclusion="Error count exceeds threshold",
            ))
            result = ClassificationResult(
                session_key=data.session_key,
                state=SessionHealthState.ERRORING,
                evidence=evidence,
                summary=(
                    f"Error count {data.error_count} >= "
                    f"{self.config.error_threshold} threshold; ERRORING"
                ),
            )
            return result

        # Rule 5: Orphaned — no task association + inactive
        if self._is_orphaned(data):
            evidence.append(SignalEvidence(
                signal_name="task_association",
                value=data.task_association,
                conclusion="No active task associated",
            ))
            evidence.append(SignalEvidence(
                signal_name="inactivity_seconds",
                value=data.inactivity_seconds,
                threshold=f">{self.config.orphan_inactive_seconds}",
                conclusion="Inactive beyond orphan timeout",
            ))
            result = ClassificationResult(
                session_key=data.session_key,
                state=SessionHealthState.ORPHANED,
                evidence=evidence,
                summary=(
                    f"No task association + inactive {data.inactivity_seconds:.0f}s exceeds "
                    f"{self.config.orphan_inactive_seconds}s; ORPHANED"
                ),
            )
            return result

        # Rule 6: Stale — inactive beyond threshold (but has a task)
        if self._is_stale(data):
            evidence.append(SignalEvidence(
                signal_name="inactivity_seconds",
                value=data.inactivity_seconds,
                threshold=f">{self.config.stale_after_seconds}",
                conclusion="Inactive beyond stale threshold",
            ))

            # Distinguish stale+active vs stale+abandoned (spec §18)
            if data.task_association == "ACTIVE":
                state = SessionHealthState.STALE  # Will get WARN action, not ARCHIVE
                summary_state = "STALE"
            else:
                state = SessionHealthState.STALE
                summary_state = "STALE"

            result = ClassificationResult(
                session_key=data.session_key,
                state=state,
                evidence=evidence,
                summary=(
                    f"Inactive {data.inactivity_seconds:.0f}s exceeds "
                    f"{self.config.stale_after_seconds}s threshold; STALE"
                ),
            )
            return result

        # Rule 7: Execution stuck
        if data.execution_state == "STUCK":
            evidence.append(SignalEvidence(
                signal_name="execution_state",
                value=data.execution_state,
                conclusion="Execution state is STUCK",
            ))
            result = ClassificationResult(
                session_key=data.session_key,
                state=SessionHealthState.STUCK,
                evidence=evidence,
                summary=f"Execution state is STUCK; classified STUCK",
            )
            return result

        # Rule 8: Default — HEALTHY
        if data.alive or data.status in ("running", "completed"):
            evidence.append(SignalEvidence(
                signal_name="status",
                value=data.status,
                conclusion="Session is alive and within all thresholds",
            ))
            result = ClassificationResult(
                session_key=data.session_key,
                state=SessionHealthState.HEALTHY,
                evidence=evidence,
                summary=f"Session {data.session_key} is healthy (status={data.status})",
            )
        else:
            evidence.append(SignalEvidence(
                signal_name="alive",
                value=data.alive,
                conclusion="Session not alive and no other signals triggered unhealthy state",
            ))
            result = ClassificationResult(
                session_key=data.session_key,
                state=SessionHealthState.UNKNOWN,
                confidence=0.5,  # Lower confidence — we don't know what's wrong
                evidence=evidence,
                summary=f"Session {data.session_key} is UNKNOWN (not alive, no other signals)",
            )

        return result

    # ===== Classification Rules =====

    def _is_active_task(self, data) -> bool:
        """Rule 1: Session has an active task association — protect it."""
        return data.task_association == "ACTIVE"

    def _context_is_oversized(self, data) -> bool:
        """Check if context size exceeds the configured threshold."""
        if data.context_size_kb is None:
            return False
        return data.context_size_kb > self.config.oversized_context_kb

    def _is_orphaned(self, data) -> bool:
        """Rule 5: No task association + inactive beyond orphan timeout."""
        if data.task_association != "NONE":
            return False
        if data.inactivity_seconds is None:
            return False
        return data.inactivity_seconds > self.config.orphan_inactive_seconds

    def _is_stale(self, data) -> bool:
        """Rule 6: Inactive beyond stale threshold."""
        if data.inactivity_seconds is None:
            return False
        return data.inactivity_seconds > self.config.stale_after_seconds


# ===== CLI — Test the classifier =====
if __name__ == "__main__":
    import argparse
    from .discoverer import SessionHealthData

    parser = argparse.ArgumentParser(description="DS-EO Health Classifier")
    parser.add_argument("--session-key", "-s", required=True, help="Session key to classify")
    parser.add_argument("--alive", default=False, action="store_true")
    parser.add_argument("--status", default="running")
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--age-seconds", type=float, default=None)
    parser.add_argument("--inactive-seconds", type=float, default=None)
    parser.add_argument("--context-kb", type=int, default=None)
    parser.add_argument("--compaction-status", default="UNDETERMINED")
    parser.add_argument("--execution-state", default="UNKNOWN")
    parser.add_argument("--error-count", type=int, default=0)
    parser.add_argument("--task-association", default="NONE")
    parser.add_argument("--recovery-history-count", type=int, default=0)
    parser.add_argument("--mapping-confidence", default="LOW")
    args = parser.parse_args()

    data = SessionHealthData(
        session_key=args.session_key,
        alive=args.alive,
        status=args.status,
        age_seconds=args.age_seconds,
        inactivity_seconds=args.inactive_seconds,
        context_size_kb=args.context_kb,
        compaction_status=args.compaction_status,
        execution_state=args.execution_state,
        error_count=args.error_count,
        task_association=args.task_association,
    )
    if args.task_id:
        data.associated_task_id = args.task_id

    classifier = HealthClassifier()
    result = classifier.classify(data)

    print(f"Session: {result.session_key}")
    print(f"State:   {result.state.value} (confidence={result.confidence})")
    print(f"Summary: {result.summary}")
    print("\nEvidence:")
    for e in result.evidence:
        print(f"  [{e.signal_name}] value={e.value}, threshold={e.threshold or '—'}, → {e.conclusion}")
