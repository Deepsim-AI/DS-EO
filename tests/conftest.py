"""Shared pytest fixtures for DS-EO Phase 5 integration tests.

Provides common setup helpers used across all Phase 5 test modules:
- Fake task directories with controlled file presence
- Config factories (manual/automatic/default)
- Selector instances pre-wired to configs
- State engine instances pre-wired to fake dirs + modes
"""

import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from ds_eo_openclaw.workflow.config import WorkflowConfig
from ds_eo_openclaw.workflow.selector import ModeSelector
from ds_eo_openclaw.workflow.state_engine import StateEngine, State


# --------------------------------------------------------------------------- #
# Fixtures — Fake Task Directories
# --------------------------------------------------------------------------- #

@pytest.fixture
def fake_task_dir(tmp_path):
    """Create a temporary task directory with simulated TASK_ naming."""
    d = tmp_path / "TASK_FAKE_001"
    d.mkdir()
    return str(d)


@pytest.fixture
def fake_task_dir_with_cto_plan(fake_task_dir):
    """Task dir with CTO_PLAN.md present (state signal for TASK_OPEN)."""
    path = os.path.join(fake_task_dir, "CTO_PLAN.md")
    with open(path, "w") as f:
        f.write("plan_content")
    return fake_task_dir


@pytest.fixture
def fake_task_dir_with_impl_report(fake_task_dir):
    """Task dir with IMPLEMENTATION_REPORT.md present (state signal for WAITING_G2)."""
    path = os.path.join(fake_task_dir, "IMPLEMENTATION_REPORT.md")
    with open(path, "w") as f:
        f.write("impl_content")
    return fake_task_dir


@pytest.fixture
def fake_task_dir_with_review_report(fake_task_dir):
    """Task dir with REVIEW_REPORT.md present (state signal for G3_PENDING)."""
    path = os.path.join(fake_task_dir, "REVIEW_REPORT.md")
    with open(path, "w") as f:
        f.write("review_content")
    return fake_task_dir


@pytest.fixture
def fake_task_dir_with_approval_approved(fake_task_dir):
    """Task dir with CTO_APPROVAL.md APPROVED (state signal for COMPLETED)."""
    path = os.path.join(fake_task_dir, "CTO_APPROVAL.md")
    with open(path, "w") as f:
        f.write("decision: APPROVED\n")
    return fake_task_dir


@pytest.fixture
def fake_task_dir_with_approval_rejected(fake_task_dir):
    """Task dir with CTO_APPROVAL.md REJECTED."""
    path = os.path.join(fake_task_dir, "CTO_APPROVAL.md")
    with open(path, "w") as f:
        f.write("decision: REJECTED\n")
    return fake_task_dir


@pytest.fixture
def full_task_dir(tmp_path):
    """Task dir with all artifact files present (signals G3_PENDING)."""
    d = tmp_path / "TASK_FULL"
    d.mkdir()
    for name in ("CTO_PLAN.md", "IMPLEMENTATION_REPORT.md", "REVIEW_REPORT.md"):
        path = os.path.join(d, name)
        with open(path, "w") as f:
            f.write("content")
    return str(d)


# --------------------------------------------------------------------------- #
# Fixtures — Config Factories
# --------------------------------------------------------------------------- #

@pytest.fixture
def manual_config():
    """WorkflowConfig in manual mode (default)."""
    return WorkflowConfig(execution_mode="manual")


@pytest.fixture
def automatic_config():
    """WorkflowConfig in automatic mode."""
    return WorkflowConfig(execution_mode="automatic")


@pytest.fixture
def default_config():
    """Default WorkflowConfig (defaults to manual, no overrides)."""
    return WorkflowConfig()


# --------------------------------------------------------------------------- #
# Fixtures — Selector Instances
# --------------------------------------------------------------------------- #

@pytest.fixture
def selector(manual_config):
    """ModeSelector wired to a manual config."""
    return ModeSelector(manual_config)


@pytest.fixture
def auto_selector(automatic_config):
    """ModeSelector wired to an automatic config."""
    return ModeSelector(automatic_config)


# --------------------------------------------------------------------------- #
# Fixtures — State Engine Instances
# --------------------------------------------------------------------------- #

@pytest.fixture
def manual_engine(fake_task_dir_with_cto_plan):
    """StateEngine in manual mode with a fake task dir."""
    return StateEngine(fake_task_dir_with_cto_plan, execution_mode="manual")


@pytest.fixture
def auto_engine(fake_task_dir_with_cto_plan):
    """StateEngine in automatic mode with a fake task dir."""
    return StateEngine(fake_task_dir_with_cto_plan, execution_mode="automatic")


# --------------------------------------------------------------------------- #
# Helpers — Temp directory cleanup
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _clean_audit_index():
    """Ensure AUDIT_INDEX.json is cleaned up between tests to avoid cross-contamination."""
    yield
    import os as _os
    _idx_path = "docs/reports/AUDIT_INDEX.json"
    if _os.path.isfile(_idx_path):
        _os.remove(_idx_path)
