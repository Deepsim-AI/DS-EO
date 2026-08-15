"""DS-EO Multi-Project Architecture — Project Resolver.

Resolves project -> agent identity + workspace for a given task or role.
Single source of truth: ~/.openclaw/ds_eo/projects.yaml (or explicit path).

Usage:
    resolver = ProjectResolver()
    info = resolver.resolve_by_task_id("TASK_DAL_002")
    # -> ProjectInfo(id='dal', agent_id='cto-dal', model=..., workspace=...)
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class AgentIdentity:
    """A resolved agent identity for a project."""
    id: str                            # e.g. "cto-dal"
    framework_agent_id: str            # e.g. "cto"
    model: str
    workspace: str
    tools_allow: list = field(default_factory=list)
    tools_deny: list = field(default_factory=list)

    def to_openclaw_entry(self) -> dict:
        """Generate an OpenClaw agents.list[] entry for this identity."""
        return {
            "id": self.id,
            "name": f"CTO / Architect ({self.id})",  # default; overridden in manifest
            "identity": {"emoji": "\U0001f3d7\ufe0f", "name": self.framework_agent_id.title()},
            "model": self.model,
            "workspace": self.workspace,
            "tools": {
                "allow": self.tools_allow or [],
                "deny": self.tools_deny or [],
            },
        }


@dataclass
class ProjectInfo:
    """Resolved information about a project."""
    id: str                              # short ID like "dal"
    name: str                            # human-readable name
    workspace: str                       # absolute path
    git_repo: str
    task_prefix: str                     # e.g. "DAL"
    agent_id_prefix: str                 # e.g. "-dal"
    artifact_paths: dict = field(default_factory=dict)  # {"reports": "...", "dispatchers": "..."}
    agents: list[AgentIdentity] = field(default_factory=list)  # resolved agent identities

    def task_report_dir(self, workspace_root_override: Optional[str] = None) -> str:
        """Path to the task reports directory for this project."""
        root = workspace_root_override or self.workspace
        return os.path.join(root, self.artifact_paths.get("reports", "docs/development/reports"))

    def task_dispatcher_dir(self, workspace_root_override: Optional[str] = None) -> str:
        """Path to the dispatcher state directory for this project."""
        root = workspace_root_override or self.workspace
        return os.path.join(root, self.artifact_paths.get("dispatchers", "docs/dispatchers"))


@dataclass
class AgentIdentityMatrix:
    """All agent identities for a given project."""
    project_id: str
    agents: dict[str, AgentIdentity]  # role -> identity (e.g. "cto" -> AgentIdentity(...))
    task_prefix: str

    def resolve_role(self, role: str) -> Optional[AgentIdentity]:
        return self.agents.get(role)


# ── Defaults ──

DEFAULT_CATALOG_PATH = os.path.join(
    os.path.expanduser("~/.openclaw"), "ds_eo", "projects.yaml"
)


# ── ProjectResolver ──

class ProjectResolver:
    """Resolve project -> agent identity + workspace mappings.

    Reads the global project catalog and provides:
      - resolve_by_task_id(): map TASK_DAL_002 -> dal -> cto-dal
      - resolve_role_for_project(): get all agents for a project
      - generate_agent_id(): "cto" + "-dal" = "cto-dal"
      - generate_openclaw_entries(): produce OpenClaw config fragments
    """

    def __init__(self, catalog_path: str = None):
        self.catalog_path = catalog_path or DEFAULT_CATALOG_PATH
        self._projects: dict[str, ProjectInfo] = {}  # id -> resolved ProjectInfo
        self._checksum: str = ""
        self._raw_data: list = []

    def load(self) -> bool:
        """Load and parse the project catalog."""
        import yaml as _yaml

        if not os.path.exists(self.catalog_path):
            return False  # No catalog; will use defaults at dispatch time

        try:
            with open(self.catalog_path) as f:
                data = _yaml.safe_load(f)
        except Exception:
            return False

        if not isinstance(data, dict) or "projects" not in data:
            return False

        projects_raw = data["projects"]
        if not isinstance(projects_raw, list):
            return False

        # Compute checksum for integrity tracking
        raw_bytes = json.dumps(projects_raw, sort_keys=True).encode("utf-8")
        self._checksum = hashlib.sha256(raw_bytes).hexdigest()
        self._raw_data = projects_raw

        # Parse each project
        self._projects = {}
        for proj in projects_raw:
            if not isinstance(proj, dict):
                continue
            project_id = proj.get("id", "")
            if not project_id:
                continue

            agents = []
            agent_defs = proj.get("default_agents", [])
            for adef in agent_defs:
                if not isinstance(adef, dict):
                    continue
                base_id = adef.get("id", "")
                prefix = proj.get("agent_id_prefix", "")
                
                # If base_id already ends with the project's suffix (e.g. "cto-dal" with "-dal"),
                # use it as-is. Otherwise append the suffix.
                if prefix and base_id.endswith(prefix):
                    resolved_id = base_id
                elif prefix:
                    resolved_id = f"{base_id}{prefix}"
                else:
                    resolved_id = base_id
                tools_allow = adef.get("tools_allow", [])
                tools_deny = adef.get("tools_deny", [])
                agent = AgentIdentity(
                    id=resolved_id,
                    framework_agent_id=base_id.split("-")[0] if prefix and base_id.endswith(prefix) else base_id,
                    model=adef.get("model", ""),
                    workspace=adef.get("workspace", ""),
                    tools_allow=tools_allow,
                    tools_deny=tools_deny,
                )
                agents.append(agent)

            project_info = ProjectInfo(
                id=project_id,
                name=proj.get("name", project_id),
                workspace=proj.get("workspace", ""),
                git_repo=proj.get("git_repo", ""),
                task_prefix=proj.get("task_prefix", project_id.upper()),
                agent_id_prefix=proj.get("agent_id_prefix", ""),
                artifact_paths=proj.get("artifact_paths", {
                    "reports": "docs/development/reports",
                    "dispatchers": "docs/dispatchers",
                }),
                agents=agents,
            )

            # Index by role for quick lookup
            agent_matrix = {}
            for a in agents:
                base_role = a.framework_agent_id
                if prefix and a.id.endswith(prefix):
                    base_role = a.id[:len(a.id) - len(prefix)]
                agent_matrix[base_role] = a

            project_info._agent_matrix = AgentIdentityMatrix(
                project_id=project_id,
                agents=agent_matrix,
                task_prefix=project_info.task_prefix,
            )

            self._projects[project_id] = project_info

        return len(self._projects) > 0

    def get_project(self, project_id: str) -> Optional[ProjectInfo]:
        """Resolve a project by its short ID."""
        if not self._projects:
            self.load()
        return self._projects.get(project_id)

    def list_projects(self) -> list[str]:
        """Return all registered project IDs."""
        if not self._projects:
            self.load()
        return list(self._projects.keys())

    def resolve_by_task_id(self, task_id: str) -> Optional[ProjectInfo]:
        """Given a TASK_ID (e.g. TASK_DAL_002), return the ProjectInfo for its project.

        Uses the task prefix convention: TASK_<PREFIX>_<NNN>.
        Falls back to scanning registered projects by workspace path if no prefix pattern matches.
        """
        if not self._projects:
            self.load()

        # Try prefix-based resolution
        import re
        match = re.match(r"TASK_(\w+)_(\d+)", task_id)
        if match:
            prefix = match.group(1).upper()
            for pid, proj in self._projects.items():
                if proj.task_prefix.upper() == prefix:
                    return proj

        # Fallback: scan all projects' workspace paths for task directories
        for pid, proj in self._projects.items():
            dispatch_dir = proj.task_dispatcher_dir()
            if os.path.isdir(dispatch_dir):
                for entry in os.listdir(dispatch_dir):
                    if entry == task_id:
                        return proj

        # Final fallback: default to the first project (framework)
        if self._projects:
            return next(iter(self._projects.values()))

        return None

    def resolve_role_for_project(self, project_id: str, role: str) -> Optional[AgentIdentity]:
        """Get the agent identity for a specific role within a project.

        Args:
            project_id: Short project ID (e.g. "dal")
            role: Framework role name (e.g. "cto", "implementer", "reviewer", "pm")

        Returns:
            AgentIdentity if found, None otherwise.
        """
        proj = self.get_project(project_id)
        if not proj or not hasattr(proj, "_agent_matrix"):
            return None
        return proj._agent_matrix.resolve_role(role)

    def generate_agent_id(self, role: str, project_id: str) -> Optional[str]:
        """Generate the full agent ID for a role within a project.

        e.g., generate_agent_id("cto", "dal") -> "cto-dal"
        """
        proj = self.get_project(project_id)
        if not proj or not proj.agent_id_prefix:
            return role  # No prefix — framework identity

        base = role
        return f"{base}{proj.agent_id_prefix}"

    def generate_openclaw_entries(self, project_id: str) -> list[dict]:
        """Generate OpenClaw agents.list[] entries for all agents in a project.

        Returns a list of dicts ready to be merged into openclaw.json['agents']['list'].
        """
        proj = self.get_project(project_id)
        if not proj or not hasattr(proj, "_agent_matrix"):
            return []

        entries = []
        for role_name in ["cto", "implementer", "reviewer", "pm"]:
            agent = proj._agent_matrix.resolve_role(role_name)
            if agent:
                entry = agent.to_openclaw_entry()
                # Fix the name field to match the actual framework role
                name_map = {
                    "cto": "CTO / Architect",
                    "implementer": "Code Implementer",
                    "reviewer": "Senior Code Reviewer",
                    "pm": "Project Manager",
                }
                entry["name"] = f"{name_map.get(role_name, role_name)} ({project_id.upper()})"
                entries.append(entry)

        return entries

    def next_task_id(self, project_id: str, workspace_root_override: Optional[str] = None) -> Optional[str]:
        """Generate the next sequential task ID for a project.

        Scans existing task directories in the project's dispatchers folder
        and returns TASK_<PREFIX>_<NNN+1>.
        Each project maintains its own independent sequence.
        """
        proj = self.get_project(project_id)
        if not proj:
            return None

        import re
        dispatch_dir = proj.task_dispatcher_dir(workspace_root_override)

        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        pattern = re.compile(r"^TASK_" + proj.task_prefix.upper() + r"_\d+$")

        max_nnn = 0
        if os.path.isdir(dispatch_dir):
            for entry in os.listdir(dispatch_dir):
                full_match = f"TASK_{proj.task_prefix.upper()}_"
                if entry.startswith(full_match) and "_" in entry:
                    try:
                        nnn_str = entry.split("_")[-1]
                        # Only match numeric suffixes after the last underscore
                        nnn = int(nnn_str)
                        if nnn > max_nnn:
                            max_nnn = nnn
                    except ValueError:
                        pass

        return f"TASK_{proj.task_prefix.upper()}_{max_nnn + 1:03d}"


# ── Convenience function ──

def resolve_project_for_task(task_id: str, catalog_path: str = None) -> Optional[ProjectInfo]:
    """One-shot convenience function."""
    resolver = ProjectResolver(catalog_path=catalog_path)
    return resolver.resolve_by_task_id(task_id)
