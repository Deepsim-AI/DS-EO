"""Tests for ds_eo_openclaw.intake.task_intake — TASK_DS_EO_029.

All tests use temporary directories via `tmp_path` fixture from conftest.py.
No integration with live gateway — purely filesystem simulation.

Fix notes (TASK_DS_EO_029):
  - Task ID format is TASK_YYYYMMDD_NNN, which splits into 3 parts on "_"
  - Jaccard DUPLICATE_THRESHOLD is 0.7; test strings must overlap enough
"""

import os
import tempfile
from pathlib import Path

import pytest
import re

from ds_eo_openclaw.intake import TaskIntakeManager
from ds_eo_openclaw.intake.task_intake import (
    _jaccard_similarity,
    _normalize_text,
)


# --------------------------------------------------------------------------- #
# Fixture
# --------------------------------------------------------------------------- #

@pytest.fixture()
def fake_workspace(tmp_path: Path) -> Path:
    """Create a minimal fake DS-EO workspace with required directory structure."""
    ws = tmp_path / "ds_eo"
    (ws / "docs").mkdir(parents=True)
    (ws / "docs" / "development" / "reports").mkdir(parents=True)
    (ws / "docs" / "dispatchers").mkdir(parents=True)
    return ws


# --------------------------------------------------------------------------- #
# 1. test_create_workspace — Spec Req 2, 3
# --------------------------------------------------------------------------- #

def test_create_workspace(fake_workspace: Path):
    """PM automatically creates task workspace (dispatcher + reports)."""
    tm = TaskIntakeManager(str(fake_workspace))
    success, result = tm.create_task_intake(
        "Add a new authentication endpoint to the API.",
    )
    assert success is True
    assert result["task_id"].startswith("TASK_")
    assert os.path.isdir(result["workspace_path"])
    assert os.path.isdir(result["dispatcher_state_path"])


# --------------------------------------------------------------------------- #
# 2. test_assigns_valid_task_id — Spec Req 3
# --------------------------------------------------------------------------- #

def test_assigns_valid_task_id(fake_workspace: Path):
    """Task ID follows TASK_YYYYMMDD_NNN convention."""
    tm = TaskIntakeManager(str(fake_workspace))
    success, result = tm.create_task_intake("Test task one")
    assert success is True
    task_id = result["task_id"]
    # Format: TASK_<YYYYMMDD>_<NNN> — three parts when split on "_"
    assert re.fullmatch(r"TASK_\d{8}_\d+", task_id), \
        f"Invalid task ID format: {task_id}"


def test_assigns_incrementing_task_ids(fake_workspace: Path):
    """Multiple tasks on the same day get incrementing NNN."""
    tm = TaskIntakeManager(str(fake_workspace))
    _, r1 = tm.create_task_intake("First task")
    _, r2 = tm.create_task_intake("Second task")
    id1 = r1["task_id"]
    id2 = r2["task_id"]
    # Parse NNN from TASK_YYYYMMDD_NNN  (last segment after final "_")
    n1 = int(id1.rsplit("_", 1)[-1])
    n2 = int(id2.rsplit("_", 1)[-1])
    assert n2 == n1 + 1, f"Expected {n1+1}, got {n2}"


# --------------------------------------------------------------------------- #
# 3. test_preserves_user_request — Spec Req 4, 5
# --------------------------------------------------------------------------- #

def test_preserves_user_request(fake_workspace: Path):
    """User's original request is preserved verbatim in TASK_REQUEST.md."""
    tm = TaskIntakeManager(str(fake_workspace))
    original = "This is my very specific and detailed request with special chars: @#$% and newlines\nand tab\there."
    success, result = tm.create_task_intake(original)
    assert success is True
    req_file = os.path.join(result["workspace_path"], "TASK_REQUEST.md")
    assert os.path.isfile(req_file)
    with open(req_file) as f:
        content = f.read()
    assert original in content


# --------------------------------------------------------------------------- #
# 4. test_separates_analysis_from_original — Spec Req 6
# --------------------------------------------------------------------------- #

def test_separates_analysis_from_original(fake_workspace: Path):
    """PM_ANALYSIS.md exists separately from TASK_REQUEST.md."""
    tm = TaskIntakeManager(str(fake_workspace))
    success, result = tm.create_task_intake("Original request", pm_analysis="PM analysis here")
    assert success is True
    analysis_file = os.path.join(result["workspace_path"], "PM_ANALYSIS.md")
    assert os.path.isfile(analysis_file)
    with open(analysis_file) as f:
        content = f.read()
    assert "PM analysis here" in content


def test_default_analysis_when_empty(fake_workspace: Path):
    """When pm_analysis is empty, a placeholder PM_ANALYSIS.md is still written."""
    tm = TaskIntakeManager(str(fake_workspace))
    success, result = tm.create_task_intake("Request without PM analysis")
    assert success is True
    analysis_file = os.path.join(result["workspace_path"], "PM_ANALYSIS.md")
    assert os.path.isfile(analysis_file)


# --------------------------------------------------------------------------- #
# 5. test_organizes_user_files — Spec Req 7
# --------------------------------------------------------------------------- #

def test_organizes_user_files(fake_workspace: Path):
    """User-provided files are stored in INPUTS/ subdirectory."""
    tm = TaskIntakeManager(str(fake_workspace))
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tf:
        tf.write("user provided content")
        tmp_file = tf.name
    try:
        success, result = tm.create_task_intake(
            "Task with attached file",
            user_files=[tmp_file],
        )
        assert success is True
        inputs_dir = os.path.join(result["workspace_path"], "INPUTS")
        assert os.path.isdir(inputs_dir)
        files_in_inputs = os.listdir(inputs_dir)
        assert len(files_in_inputs) > 0, "Expected at least one file in INPUTS/"
    finally:
        os.unlink(tmp_file)


# --------------------------------------------------------------------------- #
# 6. test_no_unnecessary_duplication — Spec Req 8
# --------------------------------------------------------------------------- #

def test_reports_workspace_location(fake_workspace: Path):
    """Result includes workspace_path that PM can report to user."""
    tm = TaskIntakeManager(str(fake_workspace))
    success, result = tm.create_task_intake("Report location test")
    assert success is True
    assert "workspace_path" in result
    assert result["workspace_path"] is not None
    assert os.path.isdir(result["workspace_path"])


# --------------------------------------------------------------------------- #
# 7. test_accepts_additional_materials — Spec Req 10, 11
# --------------------------------------------------------------------------- #

def test_add_materials_to_existing(fake_workspace: Path):
    """PM can add materials to an existing task workspace."""
    tm = TaskIntakeManager(str(fake_workspace))
    _, result = tm.create_task_intake("Initial request")
    task_id = result["task_id"]

    success, add_result = tm.add_materials_to_existing(
        task_id,
        {"notes": "Additional notes content"},
    )
    assert success is True
    assert len(add_result["added_items"]) > 0


# --------------------------------------------------------------------------- #
# 8. test_prepares_cto_handoff — Spec Req 12, 13
# --------------------------------------------------------------------------- #

def test_prepare_cto_handoff(fake_workspace: Path):
    """prepare_cto_handoff ensures CTO can read the workspace."""
    tm = TaskIntakeManager(str(fake_workspace))
    _, result = tm.create_task_intake("Task for handoff check")
    task_id = result["task_id"]

    success, handoff_result = tm.prepare_cto_handoff(task_id)
    assert success is True


def test_cto_reads_without_user_intervention(fake_workspace: Path):
    """CTO can read TASK_REQUEST.md directly from the workspace."""
    tm = TaskIntakeManager(str(fake_workspace))
    _, result = tm.create_task_intake("Direct CTO read test")

    task_req_file = os.path.join(result["workspace_path"], "TASK_REQUEST.md")
    assert os.path.isfile(task_req_file)
    with open(task_req_file) as f:
        content = f.read()
    assert len(content) > 0


# --------------------------------------------------------------------------- #
# 9. test_manual_mode_still_works — Spec Req 14
# --------------------------------------------------------------------------- #

def test_manual_mode_still_works(fake_workspace: Path):
    """Intake produces same output in manual mode."""
    tm = TaskIntakeManager(str(fake_workspace))
    success, result = tm.create_task_intake("Manual mode test", mode="manual")
    assert success is True
    assert os.path.isdir(result["workspace_path"])


# --------------------------------------------------------------------------- #
# 10. test_auto_mode_still_works — Spec Req 15
# --------------------------------------------------------------------------- #

def test_auto_mode_still_works(fake_workspace: Path):
    """Intake produces same output in auto mode."""
    tm = TaskIntakeManager(str(fake_workspace))
    success, result = tm.create_task_intake("Auto mode test", mode="automatic")
    assert success is True
    assert os.path.isdir(result["workspace_path"])


# --------------------------------------------------------------------------- #
# 11. test_prevents_duplicates — Spec Req 16
#
# NOTE: DUPLICATE_THRESHOLD = 0.7 (Jaccard keyword overlap).
# "Add user authentication to the system" vs "Implement user authentication for the API"
# has only 3/9 tokens in common = 0.33 — NOT a duplicate.
# We use much more similar strings to trigger detection correctly.
# --------------------------------------------------------------------------- #

def test_duplicate_detection(fake_workspace: Path):
    """Semantic duplicate detection works via Jaccard similarity >= threshold."""
    tm = TaskIntakeManager(str(fake_workspace))

    # Create initial task
    _, result1 = tm.create_task_intake("Add user authentication to the system")
    assert result1["duplicate_found"] is False

    # Use a near-exact phrase overlap — 75% Jaccard similarity (≥0.7 threshold)
    _, result2 = tm.create_task_intake("Implement user authentication for the API")
    # These two share tokens {user, authentication} out of union {add,user,authentication,to,the,system,implement,for,api} = 2/9 = 0.22
    # So it should NOT flag as duplicate. That's correct behavior — they ARE different tasks.
    assert result2["duplicate_found"] is False

    # Now create a true near-duplicate (high overlap): same core phrase
    _, result3 = tm.create_task_intake("Add user authentication to the system")
    assert result3["duplicate_found"] is True


def test_duplicate_detection_nearly_identical(fake_workspace: Path):
    """Very similar phrases should be detected as duplicates."""
    tm = TaskIntakeManager(str(fake_workspace))

    _, r1 = tm.create_task_intake("Login page fix needed")
    assert r1["duplicate_found"] is False

    # "Login page fix" vs "Login page fix needed" shares {login,page,fix} = 3/4 = 0.75 ≥ 0.7
    _, r2 = tm.create_task_intake("Login page fix")
    assert r2["duplicate_found"] is True


def test_find_semantic_matches(fake_workspace: Path):
    """find_semantic_matches returns matches with similarity scores."""
    tm = TaskIntakeManager(str(fake_workspace))

    # Create a task that will match our query
    _, r1 = tm.create_task_intake("Login page fix needed")
    _, r2 = tm.create_task_intake("Improve navigation menu styling")

    # "login page fix" vs "Login page fix needed" → Jaccard 3/4 = 0.75 ≥ 0.7
    matches = tm.find_semantic_matches("login page fix")
    assert len(matches) >= 1, f"Should find at least one match but got {matches}"
    assert matches[0]["task_id"] == r1["task_id"]


# --------------------------------------------------------------------------- #
# 12. test_no_source_code_access_needed — Spec Req 17
# --------------------------------------------------------------------------- #

def test_no_source_code_paths_touched(fake_workspace: Path):
    """Intake only writes to docs/ paths — never touches source code."""
    tm = TaskIntakeManager(str(fake_workspace))
    success, result = tm.create_task_intake("No-source test")

    workspace = result["workspace_path"]
    for root, dirs, files in os.walk(workspace):
        rel = os.path.relpath(root, fake_workspace)
        assert rel.startswith("docs"), f"Unexpected path outside docs/: {rel}"


# --------------------------------------------------------------------------- #
# 13. test_validates_input — boundary conditions
# --------------------------------------------------------------------------- #

def test_empty_request_raises(fake_workspace: Path):
    """Empty request_text raises ValueError."""
    tm = TaskIntakeManager(str(fake_workspace))
    with pytest.raises(ValueError, match="request_text must be non-empty"):
        tm.create_task_intake("")


def test_whitespace_request_raises(fake_workspace: Path):
    """Whitespace-only request_text raises ValueError."""
    tm = TaskIntakeManager(str(fake_workspace))
    with pytest.raises(ValueError, match="request_text must be non-empty"):
        tm.create_task_intake("   \n\t  ")


# --------------------------------------------------------------------------- #
# 14. text similarity helpers
# --------------------------------------------------------------------------- #

def test_normalize_text():
    """_normalize_text tokenizes and lowercases."""
    tokens = _normalize_text("Hello WORLD hello world")
    assert "hello" in tokens
    assert "world" in tokens


def test_jaccard_similarity_identical():
    """Jaccard of identical sets is 1.0."""
    s = {"a", "b", "c"}
    assert _jaccard_similarity(s, s) == 1.0


def test_jaccard_similarity_disjoint():
    """Jaccard of disjoint sets is 0.0."""
    assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_similarity_partial():
    """Jaccard of partial overlap is between 0 and 1."""
    similarity = _jaccard_similarity({"a", "b"}, {"b", "c"})
    assert 0 < similarity < 1


def test_jaccard_similarity_empty_sets():
    """Jaccard of two empty sets is 0.0 (avoid div-by-zero)."""
    assert _jaccard_similarity(set(), set()) == 0.0


def test_task_id_parsing_rsplit():
    """Demonstrate correct parsing of TASK_YYYYMMDD_NNN using rsplit."""
    task_id = "TASK_20260807_003"
    parts = task_id.split("_")
    assert len(parts) == 3, f"TASK ID has 3 segments: {parts}"
    nnn = int(task_id.rsplit("_", 1)[-1])
    assert nnn == 3
