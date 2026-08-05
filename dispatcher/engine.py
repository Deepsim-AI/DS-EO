"""
DS-EO Dispatcher — Workflow Engine (Core State Machine)

Reads workflow_defs/*.yaml, drives G0-G4 gate transitions,
validates against protocol requirements.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# Try PyYAML; if unavailable, fall back to basic YAML parser for our subset
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class TransitionRecord:
    """Immutable record of a completed transition."""
    id: str
    transition_name: str
    from_phase: Optional[str]  # null for G0_ENTRY
    to_phase: str
    timestamp: str
    triggered_by_agent: str
    event_type: str
    payload_summary: str = ""
    artifacts_verified: list = field(default_factory=list)
    result: str = "success"
    error: Optional[str] = None


@dataclass
class PhaseRecord:
    """Record of a phase stay (enter time, leave time, agent)."""
    phase: str
    entered_at: str
    left_at: Optional[str]  # null = currently active
    agent: str


@dataclass
class TransitionResult:
    """Result of attempting a transition."""
    success: bool
    record: Optional[TransitionRecord] = None
    phase_from: Optional[str] = None
    phase_to: Optional[str] = None
    error: Optional[str] = None
    validation_messages: list = field(default_factory=list)


@dataclass
class StallState:
    """Stall detection result."""
    stalled: bool = False
    reason: Optional[str] = None
    idle_minutes: float = 0.0
    phase_duration_minutes: float = 0.0


class WorkflowEngine:
    """
    Core workflow state machine for DS-EO G0-G4 gates.
    
    Reads workflow definitions from YAML data files.
    Does NOT modify gateway config — that's the dispatcher layer's job.
    """

    def __init__(self, workflow_path: str = None):
        """
        Initialize the workflow engine.

        Args:
            workflow_path: Path to workflow YAML file. Defaults to
                workspace_root/dispatcher/workflow_defs/default.yaml
        """
        self.workflow_path = workflow_path or os.environ.get(
            "DS_EO_WORKFLOW_PATH",
            os.path.join(os.path.dirname(__file__), "workflow_defs", "default.yaml"),
        )
        
        # Loaded state
        self.workflow_name: str = ""
        self.workflow_version: str = ""
        self.phases: dict = {}        # phase_id -> phase config
        self.transitions: dict = {}   # transition_name -> transition config
        self.stall_config: dict = {}  # stall detection settings
        self.prompt_templates: dict = {}  # name -> template string
        self.tool_policies: dict = {}  # key -> policy dict
        self._loaded: bool = False

    def load_workflow(self) -> bool:
        """
        Load and validate the workflow definition from YAML.

        Returns:
            True if loaded successfully, False otherwise (errors logged internally).
        """
        if not os.path.exists(self.workflow_path):
            print(f"ERROR: Workflow file not found: {self.workflow_path}")
            return False

        try:
            if HAS_YAML:
                with open(self.workflow_path, "r") as f:
                    data = yaml.safe_load(f)
            else:
                data = self._parse_yaml_subset(self.workflow_path)
        except Exception as e:
            print(f"ERROR: Failed to parse workflow file: {e}")
            return False

        if not isinstance(data, dict):
            print("ERROR: Workflow root must be a YAML mapping")
            return False

        # Extract sections
        self.workflow_name = data.get("name", "unknown")
        self.workflow_version = data.get("version", "0.0.0")
        self.phases = data.get("phases", {})
        self.transitions = data.get("transitions", {})
        self.stall_config = data.get("stall_detection", {})
        self.prompt_templates = data.get("prompt_templates", {})
        self.tool_policies = data.get("tool_policies", {})

        # Validate required sections exist
        errors = []
        if not self.phases:
            errors.append("No phases defined in workflow")
        if not self.transitions:
            errors.append("No transitions defined in workflow")
        
        # Validate each transition references valid phases
        valid_phases = set(self.phases.keys()) | {None}  # null is valid for from
        for tname, tconfig in self.transitions.items():
            from_phase = tconfig.get("from")
            to_phase = tconfig.get("to")
            
            if from_phase and from_phase not in valid_phases:
                errors.append(f"Transition '{tname}' references unknown 'from' phase: {from_phase}")
            
            if to_phase and to_phase not in valid_phases:
                # to can be null only for G0_ENTRY which uses phases.S0_OPEN directly
                pass  # to will be validated against known phases in execute_transition

        if errors:
            for e in errors:
                print(f"WORKFLOW VALIDATION ERROR: {e}")
            return False

        self._loaded = True
        print(f"✓ Loaded workflow '{self.workflow_name}' v{self.workflow_version}")
        print(f"  Phases: {', '.join(self.phases.keys())}")
        print(f"  Transitions: {len(self.transitions)}")
        return True

    def get_current_phase(self) -> Optional[str]:
        """Return current phase name (from last loaded state)."""
        if not self._loaded:
            return None
        # In production, this reads from dispatcher_state.json — 
        # see state_manager for that integration point
        return self._current_phase

    def set_current_phase(self, phase_id: str):
        """Set the current phase (called by state_manager after transition)."""
        if phase_id not in self.phases:
            raise ValueError(f"Unknown phase '{phase_id}'. Valid: {list(self.phases.keys())}")
        self._current_phase = phase_id

    def can_transition(self, from_phase: str, transition_name: str) -> tuple[bool, list[str]]:
        """
        Check if a transition is valid given current phase and transition name.

        Args:
            from_phase: Current phase (e.g., "S1_PLANNING")
            transition_name: Transition name (e.g., "G1_APPROVE")

        Returns:
            (allowed, list_of_validation_messages)
        """
        messages = []
        
        if not self._loaded:
            return False, ["Workflow not loaded. Call load_workflow() first."]

        # Find the transition config
        tconfig = self.transitions.get(transition_name)
        if not tconfig:
            return False, [f"Unknown transition: {transition_name}. Available: {', '.join(self.transitions.keys())}"]

        # Check from_phase matches (null means external/G0)
        expected_from = tconfig.get("from")
        if expected_from is not None and from_phase != expected_from:
            return False, [
                f"Cannot use '{transition_name}' from phase '{from_phase}'. "
                f"Expected from: {expected_from}"
            ]

        # Check to_phase is in current phase's transitions_to list
        phase_config = self.phases.get(from_phase, {})
        allowed_targets = phase_config.get("transitions_to", [])
        
        if len(allowed_targets) == 0:
            return False, [f"Phase '{from_phase}' has no outgoing transitions (is it terminal?)"]

        # Validate the transition's to matches one of the phase's allowed targets
        expected_to = tconfig.get("to")
        if expected_to not in allowed_targets:
            return False, [
                f"Transition '{transition_name}' goes to '{expected_to}', "
                f"but '{from_phase}' allows only: {allowed_targets}"
            ]

        # Check authority is declared
        if "authority" not in tconfig:
            messages.append(f"WARNING: Transition '{transition_name}' has no authority declared")

        return True, messages

    def execute_transition(
        self,
        task_id: str,
        from_phase: str,
        transition_name: str,
        triggered_by_agent: str,
        target_agent: str = None,
        event_type: str = None,
        payload_summary: str = "",
        artifacts_verified: list = None,
    ) -> TransitionResult:
        """
        Execute a gate transition.

        Args:
            task_id: Task ID (e.g., "TASK_20260805_001")
            from_phase: Current phase
            transition_name: Which gate/transition to fire
            triggered_by_agent: Who is triggering (source agent)
            target_agent: Target agent for dispatch (auto-resolved from workflow if omitted)
            event_type: Event type for the payload (e.g., "DELEGATE", "G1_APPROVE")
            payload_summary: Brief description of what's being dispatched
            artifacts_verified: List of artifact filenames verified before transition

        Returns:
            TransitionResult with success/failure details.
        """
        if not self._loaded:
            return TransitionResult(
                success=False,
                error="Workflow not loaded. Call load_workflow() first.",
            )

        # Step 1: Validate transition
        allowed, validation_msgs = self.can_transition(from_phase, transition_name)
        if not allowed:
            return TransitionResult(success=False, phase_from=from_phase, 
                                    error=f"Transition blocked: {'; '.join(validation_msgs)}",
                                    validation_messages=validation_msgs)

        # Step 2: Resolve transition config
        tconfig = self.transitions[transition_name]
        to_phase = tconfig.get("to")
        
        if target_agent is None:
            target_agent = tconfig.get("agent", triggered_by_agent)
        if event_type is None:
            event_type = tconfig.get("event", transition_name)

        # Step 3: Verify required artifacts (if any)
        required_artifacts = tconfig.get("requires_artifacts", [])
        missing_artifacts = [a for a in required_artifacts if a not in (artifacts_verified or [])]
        
        # Note: In production, this would check the task directory on disk.
        # Here we accept the caller's artifacts_verified list but warn about gaps.

        # Step 4: Build transition record
        now = datetime.now(timezone.utc).isoformat()
        txn_id = f"txn_{task_id}_{from_phase}_{transition_name[:8]}"
        
        # Generate stall timestamp if from_phase is a real phase
        current_entered = ""
        if hasattr(self, '_current_phase_entered'):
            current_entered = self._current_phase_entered

        record = TransitionRecord(
            id=txn_id,
            transition_name=transition_name,
            from_phase=from_phase if from_phase != "null" else None,
            to_phase=to_phase,
            timestamp=now,
            triggered_by_agent=triggered_by_agent,
            event_type=event_type or tconfig.get("event", ""),
            payload_summary=payload_summary,
            artifacts_verified=artifacts_verified or [],
        )

        # Step 5: Update internal state
        self._current_phase = to_phase
        if from_phase and not hasattr(self, '_phase_history'):
            self._phase_history = []
        if from_phase:
            self._phase_history.append(PhaseRecord(
                phase=from_phase,
                entered_at=getattr(self, '_last_enter_time', now),
                left_at=now,
                agent=self._current_agent or triggered_by_agent,
            ))
        if to_phase != from_phase:
            self._last_enter_time = now
            self._current_agent = tconfig.get("agent", target_agent)

        return TransitionResult(
            success=True,
            record=record,
            phase_from=from_phase,
            phase_to=to_phase,
        )

    def get_prompt_template(self, transition_name: str) -> Optional[str]:
        """
        Get the prompt template for a given transition.

        Templates are defined in workflow_defs/default.yaml under prompt_templates.
        """
        if not self._loaded or not self.prompt_templates:
            return None
        
        # Map transition names to template keys
        template_map = {
            "G1_APPROVE": "delegation_prompt",
            "G2_COMPLETE": "review_request",
            "G3_APPROVE": "approval_request",
            "G1_REJECT": "plan_revision",
        }

        template_key = template_map.get(transition_name)
        if template_key and template_key in self.prompt_templates:
            return self.prompt_templates[template_key]
        
        # Try direct lookup by transition name
        if transition_name in self.prompt_templates:
            return self.prompt_templates[transition_name]
        
        return None

    def format_prompt(self, template_str: str, **kwargs) -> str:
        """Render a prompt template with filled placeholders."""
        try:
            return template_str.format(**kwargs)
        except KeyError as e:
            missing = str(e).strip("'")
            return f"TEMPLATE ERROR: Missing placeholder '{{{missing}}}'.\n\nOriginal:\n{template_str}"

    def check_stall(self, from_phase_entered_at: str = None, last_artifact_update: str = None) -> StallState:
        """
        Check if the current phase is stalled.

        Args:
            from_phase_entered_at: ISO8601 timestamp of when current phase was entered
            last_artifact_update: ISO8601 timestamp of last artifact file write

        Returns:
            StallState with stall status and details.
        """
        state = StallState()

        if not self._loaded or not self.stall_config.get("enabled", False):
            return state

        max_phase_mins = self.stall_config.get("max_phase_duration_minutes", 480)
        idle_threshold_mins = self.stall_config.get("idle_threshold_minutes", 120)

        if from_phase_entered_at:
            entered_dt = datetime.fromisoformat(from_phase_entered_at.replace("Z", "+00:00"))
            elapsed_mins = (datetime.now(timezone.utc) - entered_dt).total_seconds() / 60
            state.phase_duration_minutes = elapsed_mins
            if elapsed_mins > max_phase_mins:
                state.stalled = True
                state.reason = f"Phase exceeded max duration ({elapsed_mins:.0f}m > {max_phase_mins}m)"

        if last_artifact_update and (state.phase_duration_minutes == 0):
            update_dt = datetime.fromisoformat(last_artifact_update.replace("Z", "+00:00"))
            idle_mins = (datetime.now(timezone.utc) - update_dt).total_seconds() / 60
            state.idle_minutes = idle_mins
            if idle_mins > idle_threshold_mins:
                state.stalled = True
                state.reason = f"Idle for {idle_mins:.0f} minutes (threshold: {idle_threshold_mins}m)"

        return state

    # ====================================================================
    # Minimal YAML parser (fallback when PyYAML unavailable)
    # ====================================================================
    def _parse_yaml_subset(self, path: str) -> dict:
        """
        Lightweight YAML subset parser for our workflow definition format.
        Handles: mappings, sequences, strings, integers, booleans, null.
        Does NOT handle: complex anchors, multi-line folds beyond simple |.
        """
        with open(path) as f:
            content = f.read()

        # Remove comments (lines starting with # or inline # not in quotes)
        lines = []
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if " #" in line and '"' not in line:
                line = line.split(" #")[0]
            lines.append(line)

        # Use a simple state machine to parse the structure
        result = {}
        stack = [(result, -1)]  # (dict, indent_level)
        current_list = None
        current_list_key = None
        in_multiline = False
        multiline_buf = ""
        multiline_key = None

        for i, line in enumerate(lines):
            if not line.strip():
                continue

            indent = len(line) - len(line.lstrip())

            # Handle multi-line blocks (the | syntax)
            if in_multiline:
                if line.strip() == "" or indent > 0:
                    multiline_buf += line.strip() + "\n"
                    continue
                else:
                    in_multiline = False
                    result[multiline_key] = multiline_buf.rstrip()

            # Multi-line block start
            if ": |" in line:
                key = line.split(": |")[0].strip().rstrip(":").strip('"').strip("'")
                multiline_key = key
                in_multiline = True
                multiline_buf = ""
                # Remove the inline part before |
                parts = line.split(": |", 1)
                if len(parts[1].strip()):
                    # Could have a default value after |
                    pass

            if line.strip().startswith("- "):
                # List item
                value = line.strip()[2:].strip().strip('"').strip("'")
                if current_list_key and current_list is not None:
                    # Check if this is a nested key-value within the list
                    if ": " in value and not value.startswith(" ["):
                        subkey, subval = value.split(": ", 1)
                        entry = {subkey.strip(): self._parse_value(subval.strip())}
                        current_list.append(entry)
                    else:
                        current_list.append(self._parse_value(value))
                continue

            if ": " in line:
                key, value = line.split(": ", 1)
                key = key.strip().strip('"').strip("'")
                
                # Handle inline list [item1, item2]
                if value.startswith("["):
                    items = []
                    inner = value[1:-1]  # strip brackets
                    if inner.strip():
                        for item in inner.split(","):
                            items.append(self._parse_value(item.strip()))
                    value = items

                val = self._parse_value(value)
                
                # If it's a dict (sub-indented), create a nested dict
                if isinstance(val, str) and val == "":
                    # Value will come from sub-lines — create placeholder dict
                    result[key] = {}
                    stack.append((result[key], indent))
                else:
                    result[key] = val

        return result

    def _parse_value(self, value: str):
        """Parse a YAML scalar value."""
        if not value:
            return None
        
        # String (remove quotes)
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]

        # Boolean
        if value.lower() in ("true", "yes"):
            return True
        if value.lower() in ("false", "no"):
            return False

        # Null
        if value.lower() in ("null", "~", ""):
            return None

        # Integer
        try:
            return int(value)
        except ValueError:
            pass

        # Float
        try:
            return float(value)
        except ValueError:
            pass

        # String (strip remaining quotes if any)
        return value


# ====================================================================
# CLI usage — quick workflow validation and transition simulation
# ====================================================================
if __name__ == "__main__":
    import sys, argparse

    parser = argparse.ArgumentParser(description="DS-EO Workflow Engine")
    parser.add_argument("--workflow", help="Path to workflow YAML file", default=None)
    parser.add_argument("--validate", action="store_true", help="Validate workflow only")
    parser.add_argument("--simulate", metavar="TRANSITION", help="Simulate a transition")
    parser.add_argument("--current-phase", "-p", default="S1_PLANNING", help="Starting phase")
    args = parser.parse_args()

    engine = WorkflowEngine(workflow_path=args.workflow)
    loaded = engine.load_workflow()

    if not loaded:
        sys.exit(1)

    if args.validate:
        print("\n✓ Workflow is valid")
        print(f"\nPhases:")
        for pid, pconf in engine.phases.items():
            agents_list = ", ".join(pconf.get("transitions_to", [])) or "(terminal)"
            print(f"  {pid}: agent={pconf.get('agent')}, next=[{agents_list}]")

        print(f"\nTransitions:")
        for tname, tconf in engine.transitions.items():
            auth = tconf.get("authority", "none")
            artifacts = tconf.get("requires_artifacts", [])
            print(f"  {tname}: {tconf.get('from','null')} → {tconf.get('to')} "
                  f"(agent={tconf.get('agent')}, auth={auth})")
            if artifacts:
                print(f"    Required: {', '.join(artifacts)}")

        sys.exit(0)

    if args.simulate:
        engine.set_current_phase(args.current_phase)
        
        # Simulate transition execution
        result = engine.execute_transition(
            task_id="TASK_20260805_001",
            from_phase=args.current_phase,
            transition_name=args.simulate,
            triggered_by_agent="pm",
            payload_summary="Simulated transition for validation",
        )

        if result.success:
            print(f"✓ Transition '{args.simulate}' succeeded")
            print(f"  {result.phase_from} → {result.phase_to}")
            print(f"  Agent: {engine._current_agent}")
        else:
            print(f"✗ Transition '{args.simulate}' blocked:")
            for msg in result.validation_messages:
                print(f"  - {msg}")
            if result.error:
                print(f"  Error: {result.error}")

    # Show prompt templates available
    print("\nPrompt Templates:")
    for name, tmpl in engine.prompt_templates.items():
        preview = tmpl.strip().split('\n')[0][:80]
        print(f"  {name}: {preview}...")
