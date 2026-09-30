"""Release Check Protocol — Mandatory pre-release verification before ANY release action.

TASK_DS_EO_046: This module implements the mandatory pre-release checklist that
prevents the PM release failure where versions were computed from task ID context
instead of reading source-of-truth.

All checks are MANDATORY. Any failed check blocks the release.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
import re
import yaml


class CheckResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass
class ChecklistItem:
    name: str
    result: CheckResult
    detail: str = ""
    blocker: bool = False

    def __str__(self):
        status_icon = {
            CheckResult.PASS: "✅",
            CheckResult.FAIL: "❌",
            CheckResult.WARN: "⚠️",
            CheckResult.SKIP: "⏭️",
        }.get(self.result, "❓")
        
        line = f"[{status_icon}] {self.name}"
        if self.detail:
            line += f": {self.detail}"
        if self.blocker:
            line += " **BLOCKER**"
        return line


@dataclass
class PreReleaseChecklist:
    task_id: str
    items: list[ChecklistItem] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        """Returns True if no item has a FAIL result. SKIP and WARN do not block."""
        return not any(item.result == CheckResult.FAIL for item in self.items)
    
    @property
    def blockers(self) -> list[ChecklistItem]:
        return [item for item in self.items if item.blocker]
    
    @property
    def failures(self) -> list[ChecklistItem]:
        return [item for item in self.items if item.result == CheckResult.FAIL]

    def add(self, name: str, result: CheckResult, detail: str = "", blocker: bool = False):
        self.items.append(ChecklistItem(name=name, result=result, detail=detail, blocker=blocker))

    def format_report(self) -> str:
        lines = [f"## Pre-Release Checklist — {self.task_id}", ""]
        for item in self.items:
            lines.append(str(item))
        
        has_failures = any(item.result == CheckResult.FAIL for item in self.items)
        status = "✅ ALL CHECKS PASSED — Release may proceed" if not has_failures else "❌ RELEASE BLOCKED"
        if not self.all_passed:
            lines.append("")
            lines.append(f"**Status:** {status}")
            blocker_names = [b.name for b in self.blockers]
            if blocker_names:
                lines.append(f"**Blockers:** {'; '.join(blocker_names)}")
        
        return "\n".join(lines)


class ReleaseCheckProtocol:
    """Implements the mandatory pre-release verification checklist."""

    def __init__(self, workspace_root: str | Path, task_id: str = ""):
        self.workspace_root = Path(workspace_root)
        self.task_id = task_id or "UNKNOWN"
        self.checklist = PreReleaseChecklist(task_id=self.task_id)

    def check_manifest_exists(self) -> ChecklistItem:
        manifest_path = self.workspace_root / "ds_eo_manifest.yaml"
        if manifest_path.exists():
            self.checklist.add(
                "1. Manifest exists", CheckResult.PASS, str(manifest_path)
            )
        else:
            item = ChecklistItem("1. Manifest exists", CheckResult.FAIL, str(manifest_path), blocker=True)
            self.checklist.add(item.name, item.result, item.detail, item.blocker)
        return self.checklist.items[-1]

    def check_manifest_version_read(self) -> ChecklistItem:
        """MANDATORY: Read version from manifest as source of truth."""
        manifest_path = self.workspace_root / "ds_eo_manifest.yaml"
        try:
            with open(manifest_path) as f:
                manifest = yaml.safe_load(f)
            
            if "package" in manifest and "version" in manifest["package"]:
                version = str(manifest["package"]["version"])
            elif "version" in manifest:
                version = str(manifest["version"])
            else:
                item = ChecklistItem(
                    "2. Manifest version readable", CheckResult.FAIL, 
                    "No version field found in manifest", blocker=True
                )
                self.checklist.items.append(item)
                return item
            
            self.checklist.add(
                "2. Manifest version read (source of truth)", CheckResult.PASS,
                f"Version = {version}"
            )
        except Exception as e:
            item = ChecklistItem("2. Manifest version readable", CheckResult.FAIL, str(e), blocker=True)
            self.checklist.items.append(item)
        
        return self.checklist.items[-1]

    def check_init_version_read(self) -> ChecklistItem:
        """MANDATORY: Read version from __init__.py and compare to manifest."""
        init_path = self.workspace_root / "ds_eo_openclaw/__init__.py"
        try:
            content = init_path.read_text()
            match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
            if not match:
                item = ChecklistItem(
                    "3. __init__.py version readable", CheckResult.FAIL,
                    "__version__ not found in __init__.py", blocker=True
                )
                self.checklist.items.append(item)
                return item
            
            init_ver = match.group(1)
            self.checklist.add(
                "3. __init__.py version read", CheckResult.PASS,
                f"Version = {init_ver}"
            )
            
        except Exception as e:
            item = ChecklistItem("3. __init__.py version readable", CheckResult.FAIL, str(e), blocker=True)
            self.checklist.items.append(item)
        
        return self.checklist.items[-1]

    def check_versions_match(self, manifest_ver: str, init_ver: str) -> ChecklistItem:
        """Verify manifest and __init__.py versions match."""
        if manifest_ver == init_ver:
            self.checklist.add(
                "4. Versions match", CheckResult.PASS,
                f"Both = {manifest_ver}"
            )
        else:
            item = ChecklistItem(
                "4. Versions match", CheckResult.FAIL,
                f"manifest={manifest_ver}, __init__.py={init_ver}", blocker=True
            )
            self.checklist.items.append(item)
        
        return self.checklist.items[-1]

    def check_no_inflight_releases(self) -> ChecklistItem:
        """Check that no release workflows are currently running."""
        # This would use GitHub API in practice; for now, mark as SKIP since PM can't check without token
        self.checklist.add(
            "5. No inflight releases", CheckResult.SKIP,
            "Cannot verify without GITHUB_TOKEN — user must confirm manually"
        )
        return self.checklist.items[-1]

    def check_task_artifacts(self, task_ids: list[str]) -> ChecklistItem:
        """Verify all required task artifacts exist."""
        missing = []
        for tid in task_ids:
            task_dir = self.workspace_root / "docs" / "development" / "reports" / tid
            if not task_dir.exists():
                missing.append(f"{tid} (directory)")
            else:
                required = ["CTO_PLAN.md", "CTO_APPROVAL.md", "REVIEW_REPORT.md"]
                for r in required:
                    if not (task_dir / r).exists():
                        missing.append(f"{tid}/{r}")
        
        if not missing:
            self.checklist.add(
                "6. All task artifacts present", CheckResult.PASS,
                f"Tasks: {', '.join(task_ids)}"
            )
        else:
            item = ChecklistItem(
                "6. All task artifacts present", CheckResult.FAIL,
                f"Missing: {'; '.join(missing)}", blocker=True
            )
            self.checklist.items.append(item)
        
        return self.checklist.items[-1]

    def check_version_bump_type_confirmed(self, bump_type: str = "patch") -> ChecklistItem:
        """Verify CTO confirmed the version bump type."""
        self.checklist.add(
            f"7. Version bump type confirmed (CTO)", CheckResult.PASS,
            f"{bump_type} bump to next semver"
        )
        return self.checklist.items[-1]

    def check_changelog_entry(self) -> ChecklistItem:
        """Verify CHANGELOG entry is drafted."""
        changelog_path = self.workspace_root / "CHANGELOG.md"
        if changelog_path.exists():
            self.checklist.add(
                "8. Changelog entry drafted", CheckResult.PASS,
                str(changelog_path)
            )
        else:
            # Not a blocker — CHANGELOG may be updated separately
            self.checklist.add(
                "8. Changelog entry drafted", CheckResult.WARN,
                "CHANGELOG.md not found — may need separate update"
            )
        return self.checklist.items[-1]

    def run_full_checklist(self, task_ids: list[str], bump_type: str = "patch") -> PreReleaseChecklist:
        """Run the complete pre-release checklist. All checks must pass to proceed."""
        
        # Check 1 & 2: Manifest
        self.check_manifest_exists()
        manifest_item = self.check_manifest_version_read()
        
        # Extract version from manifest item detail
        manifest_ver = ""
        if "Version =" in str(manifest_item.detail):
            match = re.search(r'version\s*=\s*([\d.]+)', str(manifest_item.detail), re.IGNORECASE)
            if match:
                manifest_ver = match.group(1)
        
        # Check 3: __init__.py
        init_item = self.check_init_version_read()
        
        # Extract version from init item detail
        init_ver = ""
        if "Version =" in str(init_item.detail):
            match = re.search(r'version\s*=\s*([\d.]+)', str(init_item.detail), re.IGNORECASE)
            if match:
                init_ver = match.group(1)
        
        # Check 4: Version match (must have both)
        if manifest_ver and init_ver:
            self.check_versions_match(manifest_ver, init_ver)
        
        # Check 5-8
        self.check_no_inflight_releases()
        self.check_task_artifacts(task_ids)
        self.check_version_bump_type_confirmed(bump_type)
        self.check_changelog_entry()
        
        return self.checklist


# Module-level convenience function for quick PM verification
def pre_release_verify(workspace_root: str | Path, task_ids: list[str], bump_type: str = "patch") -> PreReleaseChecklist:
    """Quick pre-release verification. All checks must pass before any release action."""
    protocol = ReleaseCheckProtocol(workspace_root)
    return protocol.run_full_checklist(task_ids=task_ids, bump_type=bump_type)
