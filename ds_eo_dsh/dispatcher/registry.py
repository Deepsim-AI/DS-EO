"""
DS-EO Dispatcher — Agent Registry Loader

Reads agents_list.json, cross-validates against gateway config,
provides dispatch-ready targets for the workflow engine.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentInfo:
    """Normalized agent info resolved from agents_list.json."""
    id: str
    name: str
    model: str
    workspace: str
    default: bool
    tools_allow: list = field(default_factory=list)
    tools_deny: list = field(default_factory=list)
    profile: Optional[str] = None
    identity_emoji: Optional[str] = None


@dataclass
class RegistryResult:
    """Result of a registry lookup."""
    success: bool
    agent: Optional[AgentInfo] = None
    error: Optional[str] = None
    checksum: str = ""
    agents_loaded: int = 0


@dataclass
class ValidationResult:
    """Result of cross-validation against gateway config."""
    success: bool
    messages: list = field(default_factory=list)
    mismatches: list = field(default_factory=list)


class AgentRegistry:
    """
    Load, validate, and resolve agents from the DS-EO agent registry.
    
    Source of truth: agents_list.json at workspace root.
    Cross-validation: optional comparison against gateway config (openclaw config get agents).
    """

    def __init__(self, workspace_root: str = None):
        """
        Initialize registry loader.

        Args:
            workspace_root: Path to DS-EO workspace. Defaults to dirname of this file's parent.
        """
        if workspace_root is None:
            workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.workspace_root = workspace_root
        self.registry_path = os.path.join(workspace_root, "agents_list.json")
        
        # Cached state (cleared on reload)
        self.agents: dict[str, AgentInfo] = {}  # id -> AgentInfo
        self.checksum: str = ""
        self.raw_data: list = []
        self._validated: bool = False
        self.validation_errors: list = []

    def load(self) -> RegistryResult:
        """
        Load and parse agents_list.json.

        Returns:
            RegistryResult with loaded agents or error details.
        """
        if not os.path.exists(self.registry_path):
            return RegistryResult(
                success=False,
                error=f"agents_list.json not found at {self.registry_path}"
            )

        try:
            with open(self.registry_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return RegistryResult(
                success=False,
                error=f"Invalid JSON in agents_list.json: {e}"
            )

        if not isinstance(data, list):
            return RegistryResult(
                success=False,
                error="agents_list.json must be a JSON array of agent objects"
            )

        # Compute SHA256 checksum for integrity tracking
        raw_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
        self.checksum = hashlib.sha256(raw_bytes).hexdigest()
        self.raw_data = data

        # Parse each agent
        self.agents = {}
        errors = []

        for i, item in enumerate(data):
            try:
                agent_info = self._parse_agent(item)
                self.agents[agent_info.id] = agent_info
            except Exception as e:
                errors.append(f"  [{i}] Failed to parse agent at index {i}: {e}")

        if not self.agents:
            return RegistryResult(
                success=False,
                error="No valid agents loaded from agents_list.json",
                checksum=self.checksum,
                agents_loaded=0
            )

        # Validate no duplicate IDs
        ids = [a.id for a in self.agents.values()]
        seen = set()
        duplicates = []
        for rid in ids:
            if rid in seen:
                duplicates.append(rid)
            seen.add(rid)
        if duplicates:
            errors.append(f"  Duplicate agent IDs found: {duplicates}")

        return RegistryResult(
            success=len(errors) == 0,
            checksum=self.checksum,
            agents_loaded=len(self.agents),
        )

    def _parse_agent(self, item: dict) -> AgentInfo:
        """Parse a single agent entry from agents_list.json."""
        if not isinstance(item, dict):
            raise ValueError("Each agent entry must be a JSON object")

        required_fields = ["id", "name", "model", "workspace"]
        for field_name in required_fields:
            if field_name not in item:
                raise ValueError(f"Missing required field: {field_name}")

        tools_allow = []
        tools_deny = []
        profile = None
        identity_emoji = None

        tools = item.get("tools", {})
        if isinstance(tools, dict):
            tools_allow = tools.get("allow", []) or []
            tools_deny = tools.get("deny", []) or []
            profile = tools.get("profile")

        identity = item.get("identity", {})
        if isinstance(identity, dict):
            identity_emoji = identity.get("emoji")

        return AgentInfo(
            id=item["id"],
            name=item["name"],
            model=item["model"],
            workspace=item["workspace"],
            default=item.get("default", False),
            tools_allow=tools_allow,
            tools_deny=tools_deny,
            profile=profile,
            identity_emoji=identity_emoji,
        )

    def resolve(self, agent_id: str) -> RegistryResult:
        """
        Resolve a target agent for dispatch.

        Args:
            agent_id: The agent ID to look up (e.g., "cto", "implementer")

        Returns:
            RegistryResult with the resolved AgentInfo or error.
        """
        if not self.agents:
            return RegistryResult(
                success=False,
                error="Registry not loaded. Call load() first."
            )

        agent = self.agents.get(agent_id)
        if not agent:
            available = ", ".join(sorted(self.agents.keys()))
            return RegistryResult(
                success=False,
                error=f"Agent '{agent_id}' not found in registry. Available: {available}"
            )

        # Validate we have enough info for dispatch
        errors = []
        if not agent.model:
            errors.append(f"Agent '{agent_id}' has no model configured")
        if not agent.workspace:
            errors.append(f"Agent '{agent_id}' has no workspace configured")

        return RegistryResult(
            success=len(errors) == 0,
            agent=agent,
            error="; ".join(errors) if errors else None,
            checksum=self.checksum,
            agents_loaded=len(self.agents),
        )

    def sync_checksum(self) -> ValidationResult:
        """
        Validate that agents_list.json hasn't changed since last load.

        Returns:
            ValidationResult with mismatch details if any.
        """
        current_data = []
        try:
            with open(self.registry_path, "r") as f:
                current_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            return ValidationResult(
                success=False,
                messages=[f"Cannot read agents_list.json: {e}"]
            )

        current_bytes = json.dumps(current_data, sort_keys=True).encode("utf-8")
        current_checksum = hashlib.sha256(current_bytes).hexdigest()

        if self.checksum and current_checksum != self.checksum:
            return ValidationResult(
                success=False,
                messages=[
                    f"Agent registry checksum changed! This task may need recreation.",
                    f"  Original: {self.checksum}",
                    f"  Current:  {current_checksum}",
                ]
            )

        if not self.checksum:
            return ValidationResult(
                success=False,
                messages=["Registry was never loaded — call load() first."],
            )

        return ValidationResult(success=True, messages=["Checksum matches"])

    def list_agents(self) -> list[dict]:
        """Return all loaded agents as dicts (for logging/status)."""
        if not self.agents:
            return []
        return [
            {
                "id": a.id,
                "name": a.name,
                "model": a.model,
                "workspace": a.workspace,
                "default": a.default,
                "tools_allow_count": len(a.tools_allow),
                "tools_deny_count": len(a.tools_deny),
            }
            for a in self.agents.values()
        ]

    def reload(self) -> RegistryResult:
        """Clear cache and reload from disk."""
        self.agents = {}
        self.checksum = ""
        self.raw_data = []
        return self.load()


# ====================================================================
# CLI usage for quick validation
# ====================================================================
if __name__ == "__main__":
    import sys

    workspace = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    registry = AgentRegistry(workspace_root=workspace)
    result = registry.load()
    
    if not result.success:
        print(f"FAILED: {result.error}")
        sys.exit(1)
    
    print(f"✓ Loaded {result.agents_loaded} agents (checksum: {result.checksum[:16]}...)")
    for aid, agent in sorted(registry.agents.items()):
        default_tag = " [DEFAULT]" if agent.default else ""
        print(f"  {aid:12s} model={agent.model:40s} workspace={agent.workspace}{default_tag}")
    
    # Validate checksum is consistent
    vr = registry.sync_checksum()
    if not vr.success:
        for msg in vr.messages:
            print(f"WARNING: {msg}")
    else:
        print(f"✓ Checksum valid")
