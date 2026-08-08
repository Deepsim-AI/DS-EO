"""
DS-EO Session Health — Public API (Phase 2: Health Classification)

A small, reliable operational layer around OpenClaw's existing session capabilities.
Provides health discovery → classification → policy.

Usage:
    from ds_eo_openclaw.session_health import (
        HealthClassifier,
        MonitorStatus,
        get_default_config,
    )

    classifier = HealthClassifier(get_default_config())
    result = classifier.classify(session_data)
"""

from .enums import SessionHealthState, LifecycleAction, MonitorStatus, HealthSignal
from .config import SessionHealthConfig, get_default_config
from .discoverer import SessionDiscoverer, SessionHealthData
from .classifier import HealthClassifier, ClassificationResult
from .policy import HealthPolicy, PolicyDecision
from .executor import SessionHealthExecutor, ActionResult
from .monitor import SessionHealthMonitor, CycleReport, SessionActionRecord
from .audit import SessionHealthAuditLog, SessionHealthAuditEvent

__all__ = [
    "SessionHealthState",
    "LifecycleAction",
    "MonitorStatus",
    "HealthSignal",
    "SessionHealthConfig",
    "get_default_config",
    "SessionDiscoverer",
    "SessionHealthData",
    "HealthClassifier",
    "ClassificationResult",
    "HealthPolicy",
    "PolicyDecision",
    "SessionHealthExecutor",
    "ActionResult",
    "SessionHealthMonitor",
    "CycleReport",
    "SessionActionRecord",
    "SessionHealthAuditLog",
    "SessionHealthAuditEvent",
]
