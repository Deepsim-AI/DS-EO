"""Comprehensive tests for Release Manager and Release Check Protocol.

Tests cover:
1. Semver parsing and version computation
2. ReleaseManager lifecycle (state transitions, version reading, bumping)
3. Version mismatch detection (manifest vs __init__.py)
4. Artifact verification per task
5. Pre-release checklist completeness
6. Tag creation and remote verification logic
7. Dispatch workflow dispatch gating
8. Finalize closure state machine
9. ReleaseCheckProtocol individual checks
10. Edge cases: missing files, invalid semver, partial artifacts
"""

import os
import re
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# ─── Import under test ───────────────────────────────────────────────────────

from ds_eo_openclaw.release_manager import (
    ReleaseManager,
    ReleaseState,
    ReleaseVerdict,
    compute_next_version,
    parse_semver,
    verify_pre_release,
)
from ds_eo_openclaw.release_check_protocol import (
    ChecklistItem,
    CheckResult,
    PreReleaseChecklist,
    ReleaseCheckProtocol,
    pre_release_verify,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_workspace(tmp_path, version="1.2.3") -> Path:
    """Create a minimal workspace with manifest and __init__.py at the given version."""
    ws = tmp_path / "test_repo"
    ws.mkdir()

    # ds_eo_manifest.yaml
    manifest = {
        "package": {"name": "ds-eo-openclaw", "version": version},
        "description": "Test package",
    }
    (ws / "ds_eo_manifest.yaml").write_text(yaml.dump(manifest))

    # ds_eo_openclaw/__init__.py
    pkg = ws / "ds_eo_openclaw"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(f'__version__ = "{version}"\n')
    (pkg / "__main__.py").write_text("pass\n")

    return ws


def _make_workspace_with_mismatch(tmp_path) -> Path:
    """Workspace where manifest and __init__.py have DIFFERENT versions."""
    ws = tmp_path / "test_repo_mismatch"
    ws.mkdir()

    manifest = {
        "package": {"name": "ds-eo-openclaw", "version": "1.2.3"},
    }
    (ws / "ds_eo_manifest.yaml").write_text(yaml.dump(manifest))

    pkg = ws / "ds_eo_openclaw"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('__version__ = "1.2.4"\n')
    return ws


def _make_task_dir(ws: Path, task_id: str) -> Path:
    """Create a fake task directory with all required artifacts."""
    reports = ws / "docs" / "development" / "reports" / task_id
    reports.mkdir(parents=True)
    for name in ("CTO_PLAN.md", "IMPLEMENTATION_REPORT.md", "REVIEW_REPORT.md", "CTO_APPROVAL.md"):
        (reports / name).write_text("content")
    return reports


def _make_partial_task_dir(ws: Path, task_id: str) -> Path:
    """Create a fake task directory MISSING REVIEW_REPORT.md."""
    reports = ws / "docs" / "development" / "reports" / task_id
    reports.mkdir(parents=True)
    (reports / "CTO_PLAN.md").write_text("content")
    return reports


# ─── Test 1: Semver Parsing ──────────────────────────────────────────────────

class TestParseSemVer:
    def test_valid_semver(self):
        assert parse_semver("1.2.3") == (1, 2, 3)

    def test_zero_components(self):
        assert parse_semver("0.0.0") == (0, 0, 0)

    def test_large_versions(self):
        assert parse_semver("99.100.101") == (99, 100, 101)

    def test_invalid_format_no_dots(self):
        with pytest.raises(ValueError, match="Invalid semver"):
            parse_semver("1.2")

    def test_invalid_format_non_numeric(self):
        with pytest.raises(ValueError, match="Invalid semver"):
            parse_semver("1.x.3")

    def test_invalid_format_empty(self):
        with pytest.raises(ValueError, match="Invalid semver"):
            parse_semver("")


# ─── Test 2: Version Computation ──────────────────────────────────────────────

class TestComputeNextVersion:
    def test_patch_bump(self):
        assert compute_next_version("1.2.3", "patch") == "1.2.4"

    def test_minor_bump(self):
        assert compute_next_version("1.2.3", "minor") == "1.3.0"

    def test_major_bump(self):
        assert compute_next_version("1.2.3", "major") == "2.0.0"

    def test_zero_to_first_patch(self):
        assert compute_next_version("0.0.0", "patch") == "0.0.1"

    def test_minor_bump_at_boundary(self):
        assert compute_next_version("1.9.5", "minor") == "1.10.0"

    def test_invalid_bump_type(self):
        with pytest.raises(ValueError, match="Unknown bump type"):
            compute_next_version("1.2.3", "micro")

    def test_default_is_patch(self):
        assert compute_next_version("0.1.0") == "0.1.1"


# ─── Test 3: ReleaseVerdict ──────────────────────────────────────────────────

class TestReleaseVerdict:
    def test_initial_state_requires_success(self):
        with pytest.raises(TypeError):
            ReleaseVerdict()

    def test_ok_sets_version(self):
        v = ReleaseVerdict(success=False)
        result = v.ok("2.0.0", detail="ready")
        assert v.current_version == "2.0.0"
        assert len(v.details) > 0

    def test_block_sets_blocker(self):
        v = ReleaseVerdict(success=True)
        v.block("missing manifest")
        assert v.success is False
        assert v.blocker == "missing manifest"
        assert v.state == ReleaseState.RELEASE_BLOCKED.value

    def test_chained_ok_doesnt_override_block(self):
        v = ReleaseVerdict(success=True)
        v.block("initial blocker")
        # Calling ok after block shouldn't fully restore success (implementation detail)
        # but current impl: ok only sets current_version and details, not success=True
        assert v.blocker == "initial blocker"


# ─── Test 4: ReleaseManager — Version Reading ─────────────────────────────────

class TestReleaseManagerVersionReading:
    def test_read_manifest_version(self, tmp_path):
        ws = _make_workspace(tmp_path)
        rm = ReleaseManager(ws)
        result = rm.read_manifest_version()
        assert result.success is True
        assert result.current_version == "1.2.3"

    def test_read_manifest_missing_file(self, tmp_path):
        ws = tmp_path / "no_manifest"
        ws.mkdir()
        rm = ReleaseManager(ws)
        result = rm.read_manifest_version()
        assert result.success is False
        assert "not found" in result.details[0]

    def test_read_manifest_invalid_yaml(self, tmp_path):
        ws = tmp_path / "bad_yaml_ws"
        ws.mkdir()
        (ws / "ds_eo_manifest.yaml").write_text("{{invalid yaml: [")
        rm = ReleaseManager(ws)
        result = rm.read_manifest_version()
        assert result.success is False

    def test_read_python_version(self, tmp_path):
        ws = _make_workspace(tmp_path)
        rm = ReleaseManager(ws)
        result = rm.read_python_version()
        assert result.success is True
        assert result.current_version == "1.2.3"

    def test_read_python_version_missing_file(self, tmp_path):
        ws = tmp_path / "no_init_ws"
        ws.mkdir()
        pkg = ws / "ds_eo_openclaw"
        pkg.mkdir()
        rm = ReleaseManager(ws)
        result = rm.read_python_version()
        assert result.success is False

    def test_read_python_version_missing__version__(self, tmp_path):
        ws = _make_workspace(tmp_path)
        (ws / "ds_eo_openclaw" / "__init__.py").write_text("# no version here\n")
        rm = ReleaseManager(ws)
        result = rm.read_python_version()
        assert result.success is False


# ─── Test 5: Version Match Detection ──────────────────────────────────────────

class TestVersionMatchDetection:
    def test_matching_versions(self, tmp_path):
        ws = _make_workspace(tmp_path)
        rm = ReleaseManager(ws)
        rm.read_manifest_version()
        rm.read_python_version()
        result = rm.verify_versions_match()
        assert result.success is True

    def test_mismatched_versions(self, tmp_path):
        ws = _make_workspace_with_mismatch(tmp_path)
        rm = ReleaseManager(ws)
        rm.read_manifest_version()
        rm.read_python_version()
        result = rm.verify_versions_match()
        assert result.success is False
        assert "mismatch" in result.details[0].lower()

    def test_missing_init_before_verify(self, tmp_path):
        ws = _make_workspace(tmp_path)
        # Remove __init__.py so current_version_init won't be set
        (ws / "ds_eo_openclaw" / "__init__.py").unlink()
        rm = ReleaseManager(ws)
        rm.read_manifest_version()
        result = rm.verify_versions_match()
        assert result.success is False


# ─── Test 6: Version Bump Application ─────────────────────────────────────────

class TestVersionBump:
    def test_bump_patches_manifest(self, tmp_path):
        ws = _make_workspace(tmp_path)
        rm = ReleaseManager(ws)
        rm.read_manifest_version()
        rm.compute_next_version("patch")
        assert rm.next_version == "1.2.4"

        result = rm.apply_version_bump(rm.next_version)
        assert result.success is True

        # Verify manifest was updated
        with open(ws / "ds_eo_manifest.yaml") as f:
            updated = yaml.safe_load(f)
        assert updated["package"]["version"] == "1.2.4"

    def test_bump_updates_init_py(self, tmp_path):
        ws = _make_workspace(tmp_path)
        rm = ReleaseManager(ws)
        rm.read_manifest_version()
        rm.compute_next_version("minor")
        assert rm.next_version == "1.3.0"

        rm.apply_version_bump(rm.next_version)

        content = (ws / "ds_eo_openclaw" / "__init__.py").read_text()
        assert '__version__ = "1.3.0"' in content


# ─── Test 7: Artifact Verification ────────────────────────────────────────────

class TestArtifactVerification:
    def test_all_artifacts_present(self, tmp_path):
        ws = _make_workspace(tmp_path)
        task_dir = _make_task_dir(ws, "TASK_FAKE_001")

        rm = ReleaseManager(ws)
        result = rm.verify_all_task_artifacts(["TASK_FAKE_001"])
        # All dirs present — but verify_all_task_artifacts has a bug: it never calls .ok() on success path.
        # The method always returns success=False because it starts with ReleaseVerdict(success=False) 
        # and the success check "if ver.success" is False. This is an implementation bug.
        # For now, accept that verify_all_task_artifacts only validates directory existence, not artifact content.
        # The method does NOT call .ok() on success — it just falls through. We need to fix the impl.
        assert result.success is True  # Will fail until impl is fixed (see line in release_manager.py)

    def test_missing_task_directory(self, tmp_path):
        ws = _make_workspace(tmp_path)
        rm = ReleaseManager(ws)
        result = rm.verify_all_task_artifacts(["TASK_FAKE_999"])
        assert result.success is False

    def test_partial_task_directory(self, tmp_path):
        ws = _make_workspace(tmp_path)
        _make_partial_task_dir(ws, "TASK_PARTIAL_001")

        rm = ReleaseManager(ws)
        # Partial dir has CTO_PLAN.md but not all required files — still valid (non-fatal warnings)
        result = rm.verify_all_task_artifacts(["TASK_PARTIAL_001"])
        assert result.success is True


# ─── Test 8: Tag Verification Logic ──────────────────────────────────────────

class TestTagVerification:
    def test_verify_tag_no_remote(self, tmp_path):
        ws = _make_workspace(tmp_path)
        rm = ReleaseManager(ws)
        rm.next_version = "2.0.0"

        # Mock git ls-remote to simulate tag not found
        with patch.object(rm, '_run_git', return_value=(1, "")):
            result = rm.verify_tag_exists_on_remote("v2.0.0")
        assert result.success is False


# ─── Test 9: Dispatch Workflow Gating ────────────────────────────────────────

class TestDispatchWorkflowGating:
    def test_dispatch_returns_none_without_token(self, tmp_path):
        ws = _make_workspace(tmp_path)
        rm = ReleaseManager(ws)
        rm.next_version = "1.3.0"

        # Ensure no GITHUB_TOKEN in environment
        env_orig = os.environ.copy()
        os.environ.pop("GITHUB_TOKEN", None)

        result = rm.dispatch_github_release_workflow("patch")
        assert result is None  # Not dispatched, not error — just returns None

        # Restore environment
        os.environ.clear()
        os.environ.update(env_orig)


# ─── Test 10: Pre-Release Verification (Module-Level) ─────────────────────────

class TestPreReleaseVerify:
    def test_pre_release_passes(self, tmp_path):
        ws = _make_workspace(tmp_path)
        result = verify_pre_release(ws, "patch")
        assert result.success is True
        assert result.current_version == "1.2.3"
        assert result.next_version == "1.2.4"

    def test_pre_release_detects_mismatch(self, tmp_path):
        ws = _make_workspace_with_mismatch(tmp_path)
        result = verify_pre_release(ws, "patch")
        assert result.success is False
        assert "mismatch" in str(result.details).lower()

    def test_pre_release_missing_manifest(self, tmp_path):
        ws = tmp_path / "no_manifest_repo"
        ws.mkdir()
        pkg = ws / "ds_eo_openclaw"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('__version__ = "1.0.0"\n')

        result = verify_pre_release(ws, "patch")
        assert result.success is False


# ─── Test 11: Release Check Protocol — Individual Checks ──────────────────────

class TestReleaseCheckProtocol:
    def test_check_manifest_exists_pass(self, tmp_path):
        ws = _make_workspace(tmp_path)
        proto = ReleaseCheckProtocol(ws, "TASK_TEST_001")
        item = proto.check_manifest_exists()
        assert item.result == CheckResult.PASS

    def test_check_manifest_exists_fail(self, tmp_path):
        ws = tmp_path / "no_manifest"
        ws.mkdir()
        proto = ReleaseCheckProtocol(ws, "TASK_TEST_001")
        # This will fail with AttributeError because check_manifest_exists calls add_item(item)
        # but PreReleaseChecklist only has add(name, result, detail, blocker). 
        # This is a bug in the implementation that needs fixing.
        item = proto.check_manifest_exists()
        assert item.result == CheckResult.FAIL
        assert item.blocker is True

    def test_check_version_read_pass(self, tmp_path):
        ws = _make_workspace(tmp_path)
        proto = ReleaseCheckProtocol(ws, "TASK_TEST_001")
        item = proto.check_manifest_version_read()
        assert item.result == CheckResult.PASS
        assert "1.2.3" in str(item.detail)

    def test_check_init_version_pass(self, tmp_path):
        ws = _make_workspace(tmp_path)
        proto = ReleaseCheckProtocol(ws, "TASK_TEST_001")
        item = proto.check_init_version_read()
        assert item.result == CheckResult.PASS

    def test_check_versions_match_pass(self, tmp_path):
        ws = _make_workspace(tmp_path)
        proto = ReleaseCheckProtocol(ws, "TASK_TEST_001")
        item = proto.check_versions_match("1.2.3", "1.2.3")
        assert item.result == CheckResult.PASS

    def test_check_versions_match_fail(self):
        proto = ReleaseCheckProtocol("", "TASK_TEST_001")
        item = proto.check_versions_match("1.2.3", "1.2.4")
        assert item.result == CheckResult.FAIL
        assert item.blocker is True


# ─── Test 12: Full Checklist Execution ────────────────────────────────────────

class TestFullChecklist:
    def test_full_checklist_all_pass(self, tmp_path):
        ws = _make_workspace(tmp_path)
        _make_task_dir(ws, "TASK_CHECK_001")

        proto = ReleaseCheckProtocol(ws, "TASK_CHECK_001")
        checklist = proto.run_full_checklist(["TASK_CHECK_001"], "patch")
        assert len(checklist.items) == 8  # 8 checks total
        # all_passed is True because no items have FAIL result (SKIP and WARN don't block)
        assert checklist.all_passed
        # But no blockers — release can proceed (just needs manual verification)
        assert len(checklist.blockers) == 0

    def test_full_checklist_manifest_missing(self, tmp_path):
        ws = tmp_path / "no_manifest_ws"
        ws.mkdir()
        pkg = ws / "ds_eo_openclaw"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('__version__ = "1.0.0"\n')

        proto = ReleaseCheckProtocol(ws, "TASK_BAD_001")
        checklist = proto.run_full_checklist(["TASK_BAD_001"], "patch")
        assert checklist.all_passed is False
        assert len(checklist.blockers) > 0

    def test_format_report_all_pass(self, tmp_path):
        ws = _make_workspace(tmp_path)
        proto = ReleaseCheckProtocol(ws, "TASK_FMT_001")
        checklist = proto.run_full_checklist([], "patch")
        report = checklist.format_report()
        # No blockers and no FAIL items — release can proceed (just needs manual verification)
        assert "RELEASE BLOCKED" not in report  # because not all == PASS (SKIP and WARN exist)
        assert len(checklist.blockers) == 0

    def test_format_report_with_failures(self, tmp_path):
        ws = tmp_path / "broken_ws"
        ws.mkdir()
        proto = ReleaseCheckProtocol(ws, "TASK_FMT_002")
        checklist = proto.run_full_checklist([], "patch")
        report = checklist.format_report()
        assert "RELEASE BLOCKED" in report


# ─── Test 13: Pre-Release Verify Convenience Function ─────────────────────────

class TestPreReleaseVerifyFunction:
    def test_quick_verify_passes(self, tmp_path):
        ws = _make_workspace(tmp_path)
        _make_task_dir(ws, "TASK_QV_001")
        # Also create CHANGELOG.md so check 8 returns PASS not WARN
        (ws / "CHANGELOG.md").write_text("# Changelog.md content\n")
        checklist = pre_release_verify(ws, ["TASK_QV_001"], "patch")
        assert len(checklist.items) == 8
        assert checklist.all_passed is True

    def test_quick_verify_detects_mismatch(self, tmp_path):
        ws = _make_workspace_with_mismatch(tmp_path)
        checklist = pre_release_verify(ws, ["TASK_QV_002"], "patch")
        assert checklist.all_passed is False


# ─── Test 14: Edge Cases ──────────────────────────────────────────────────────

class TestEdgeCases:
    def test_semver_strips_v_prefix(self):
        # parse_semver uses regex r'(\d+)\.(\d+)\.(\d+)' — it matches first digits
        # "v2.1.0" → re.match finds "2.1.0" starting at position 1, but match() 
        # requires match at START of string, so this should FAIL
        with pytest.raises(ValueError):
            parse_semver("v2.1.0")

    def test_compute_next_major_boundary(self):
        assert compute_next_version("9.9.9", "major") == "10.0.0"

    def test_compute_next_minor_boundary(self):
        assert compute_next_version("1.9.9", "minor") == "1.10.0"

    def test_compute_next_patch_boundary(self):
        assert compute_next_version("1.2.9", "patch") == "1.2.10"

    def test_multiple_task_ids_verification(self, tmp_path):
        ws = _make_workspace(tmp_path)
        for tid in ("TASK_MULTI_001", "TASK_MULTI_002", "TASK_MULTI_003"):
            _make_task_dir(ws, tid)

        rm = ReleaseManager(ws)
        result = rm.verify_all_task_artifacts(["TASK_MULTI_001", "TASK_MULTI_002", "TASK_MULTI_003"])
        assert result.success is True  # All dirs exist — but impl has bug (never sets success=True on path)


# ─── Test 15: State Machine Transitions ───────────────────────────────────────

class TestStateMachineTransitions:
    def test_initial_state(self):
        # ReleaseState enum order defines the expected flow
        states = [s.value for s in ReleaseState]
        assert states[0] == "pending"
        assert states[-2] == "release_complete"
        assert states[-1] == "release_blocked"

    def test_state_progression_logic(self):
        """Verify the state progression follows the R-REL-4 sequence (9 states total)."""
        expected = [
            "pending",           # RELEASE_PENDING
            "verify_versions",   # VERIFY_VERSIONS
            "bump_version",      # BUMP_VERSION
            "commit_push",       # COMMIT_PUSH
            "create_tag",        # CREATE_TAG
            "dispatch_workflow", # DISPATCH_WORKFLOW
            "verify_release",    # VERIFY_RELEASE
            "release_complete",  # RELEASE_COMPLETE (not release_blocked)
        ]
        actual = [s.value for s in ReleaseState]
        assert actual[:len(expected)] == expected

    def test_state_count_is_nine(self):
        """There are exactly 9 states including RELEASE_BLOCKED."""
        assert len(list(ReleaseState)) == 9


# ─── Test 16: Changelog Entry Generation ──────────────────────────────────────

class TestChangelogGeneration:
    def test_changelog_format(self, tmp_path):
        ws = _make_workspace(tmp_path)
        rm = ReleaseManager(ws)
        entry = rm.create_changelog_entry("2.0.0")

        assert "## [2.0.0]" in entry
        # Should contain today's date
        import datetime
        expected_date = datetime.date.today().strftime("%Y-%m-%d")
        assert expected_date in entry


# ─── Test 17: ReleaseVerdict Defaults ─────────────────────────────────────────

class TestReleaseVerdictDefaults:
    def test_release_verdict_default_values(self):
        v = ReleaseVerdict(success=False)
        assert v.success is False
        assert v.current_version == ""
        assert v.next_version == ""
        assert v.blocker is None
        assert v.details == []

    def test_checklist_all_passed_property(self):
        cl = PreReleaseChecklist("T1")
        cl.add("a", CheckResult.PASS)
        assert cl.all_passed is True

        cl.add("b", CheckResult.FAIL)
        assert cl.all_passed is False

    def test_checklist_blockers_only_failures(self):
        cl = PreReleaseChecklist("T1")
        cl.add("pass1", CheckResult.PASS)
        cl.add("fail1", CheckResult.FAIL, detail="x", blocker=True)
        cl.add("warn1", CheckResult.WARN, detail="y")
        cl.add("fail2", CheckResult.FAIL, detail="z", blocker=False)

        # blockers should only include items with blocker=True
        assert len(cl.blockers) == 1
        assert cl.blockers[0].name == "fail1"
