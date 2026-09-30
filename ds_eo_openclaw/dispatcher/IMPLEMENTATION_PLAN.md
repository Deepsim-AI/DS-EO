# DS-EO Dispatcher — Implementation Plan

**Version**: 0.1.0  
**Author**: CTO (architectural design)  
**Owner**: PM (execution coordination)  

---

## Executive Summary

This plan converts the Dispatcher architecture (ARCHITECTURE.md), workflow definition (workflow_defs/default.yaml), protocol (PROTOCOL.md), and state schema (STATE_SCHEMA.md) into executable work. The Dispatcher replaces manual agent coordination with a programmatic engine that:

1. Reads workflow definitions from YAML data files (not code or gateway config)
2. Uses the agent registry to resolve routing targets
3. Spawns agent sessions via OpenClaw's `sessions_spawn` API
4. Persists all state in task directories (survives restarts)
5. Keeps all routing logic inside DS-EO, not in OpenClaw config

**Gateway bindings are minimal** — only entry points (`/eo.*` commands). No internal routing lives there.

---

## Phase 0: Foundation (No code changes needed yet)

| Item | Status | Notes |
|------|--------|-------|
| ARCHITECTURE.md | ✅ Created | Full design document |
| workflow_defs/default.yaml | ✅ Created | Data-driven gate machine definition (273 lines) |
| PROTOCOL.md | ✅ Created | Runtime contract between dispatcher components |
| STATE_SCHEMA.md | ✅ Created | Persistent state file formats |
| `agentToAgent.enabled` in gateway config | ✅ Applied | Done in previous step |

**Gateway bindings?** Not yet. They are a separate concern — entry points only, no workflow logic. Will be added in Phase 2 when needed.

---

## Phase 1: Core Engine (Python Implementation)

### Step 1.1: Agent Registry Loader (`registry.py`)

**Goal**: Load and validate agents from `agents_list.json`

```python
# dispatcher/registry.py — conceptual structure
class AgentRegistry:
    def __init__(self, path="agents_list.json"):
        self.path = path
        self.agents = {}        # id -> agent info dict
        self.checksum = None
    
    def load(self):
        # Read agents_list.json, compute SHA256 checksum
        # Cross-validate against gateway config if available
        pass
    
    def resolve(self, agent_id):
        # Return dispatch-ready target for an agent ID
        pass
    
    def validate_transition_authority(self, source_agent, target_agent, transition_name):
        # Check if the transition is allowed per workflow definition
        pass
    
    def sync_checksum(self):
        # Re-validate checksum; raises if agents_list.json changed
        pass
```

**Tasks**:
1. [ ] Create `dispatcher/registry.py` module
2. [ ] Implement JSON loading + SHA256 checksum of agents_list.json
3. [ ] Implement `resolve(agent_id)` → dispatch target dict
4. [ ] Implement authority validation per workflow transitions
5. [ ] Write unit tests

### Step 1.2: Workflow Engine (`engine.py`)

**Goal**: State machine that drives G0-G4 transitions

```python
# dispatcher/engine.py — conceptual structure
class WorkflowEngine:
    def __init__(self, workflow_path="workflow_defs/default.yaml"):
        self.workflow = self._load_workflow(workflow_path)
        self.registry = AgentRegistry()
        self.state_mgr = None  # initialized per task
    
    def load_workflow(self):
        # Read default.yaml, validate schema
        pass
    
    def get_current_phase(self, task_id):
        # Read dispatcher_state.json for current phase
        pass
    
    def can_transition(self, task_id, transition_name):
        # Check: valid transition from current phase?
        # Check: all requires_artifacts present?
        # Check: authority matches?
        pass
    
    def execute_transition(self, task_id, transition_name, source_agent, payload=None):
        # 1. Validate transition (can_transition)
        # 2. Update state (state_mgr)
        # 3. Generate prompt from template (get_prompt_template(transition))
        # 4. Dispatch via session_dispatch
        # 5. Log to dispatch_log.jsonl
        pass
    
    def get_prompt_template(self, transition_name):
        # Look up in workflow YAML prompt_templates
        pass
    
    def check_stalls(self, task_id):
        # Compare current_phase_entered against idle_threshold_minutes
        # If stalled → create TASK_STALLED event
        pass
```

**Tasks**:
1. [ ] Create `dispatcher/engine.py` module
2. [ ] Implement YAML workflow loader with validation
3. [ ] Implement phase lookup and transition validation
4. [ ] Implement prompt template resolution and rendering
5. [ ] Implement stall detection logic
6. [ ] Write unit tests (especially invalid transition rejection)

### Step 1.3: State Manager (`state_manager.py`)

**Goal**: Persistent per-task state with atomic writes

```python
# dispatcher/state_manager.py — conceptual structure
class TaskStateManager:
    def __init__(self, task_id):
        self.task_id = task_id
        self.base_path = f"docs/dispatcher/{task_id}"
    
    def create_state(self, current_phase, agent_registry_snapshot):
        # Create state file with initial data
        pass
    
    def get_state(self):
        # Read and validate state file
        pass
    
    def update_phase(self, new_phase, transition_record):
        # Update current_phase, add to phase_history and transition_history
        # Atomic write (write to temp, rename)
        pass
    
    def append_dispatch_log(self, event_record):
        # Append JSON line to dispatch_log.jsonl
        pass
    
    def mark_complete(self):
        # Set completed_at timestamp, update INDEX.md
        pass
    
    def validate_registry_checksum(self, current_checksum):
        # Compare against stored checksum; alert if mismatched
        pass
```

**Tasks**:
1. [ ] Create `dispatcher/state_manager.py` module
2. [ ] Implement create/read/update state methods
3. [ ] Implement atomic file writes (temp file + rename)
4. [ ] Implement dispatch log appender
5. [ ] Write unit tests

---

## Phase 2: Session Dispatch Layer

### Step 2.1: Session Dispatch (`session_dispatch/engine.py`)

**Goal**: Wrap OpenClaw `sessions_spawn` for clean agent handoffs

```python
# dispatcher/session_dispatch/engine.py — conceptual structure
class SessionDispatcher:
    def __init__(self):
        self._agent_map = None  # lazy-loaded from registry
    
    def dispatch(self, target_agent_id, prompt_text, task_id=None):
        """
        Spawn a new agent session with the given prompt.
        Uses sessions_spawn(agent='target', context='isolated') internally.
        
        Returns: {
            "session_key": "agent:implementer:subagent:uuid",
            "status": "spawned" | "failed",
            "error": null or error_string
        }
        """
        pass
    
    def get_prompt_for_transition(self, transition_name, task_id, payload):
        """Render the prompt template for a given transition with filled placeholders."""
        pass
    
    def send_completion_notification(self, source_agent, target_agent_id, session_key):
        """Notify the target agent that work has been dispatched (post-spawn)."""
        # For non-blocking: dispatcher doesn't need this since sessions_spawn
        # is push-based and completion arrives back to parent session
        pass
```

**Tasks**:
1. [ ] Create `dispatcher/session_dispatch/engine.py` module
2. [ ] Implement spawn wrapper with isolated context
3. [ ] Implement prompt template renderer (Jinja2 or string formatting)
4. [ ] Wire into engine.execute_transition()
5. [ ] Write integration tests

---

## Phase 3: Integration — PM Agent Gets Dispatcher Skill

### Step 3.1: Update PM Agent Config

The PM agent needs a dispatcher skill that teaches it how to use the engine:

**Tasks**:
1. [ ] Create `dispatcher/SKILL.md` — PM-facing skill instructions
2. [ ] Add dispatcher skill to PM's `agents_list.json` entry (or global defaults)
3. [ ] Update PM's agent prompt (`agents/pm.md`) to include dispatcher workflow
4. [ ] Test: PM can spawn a task end-to-end

### Step 3.2: Skill Content — What the PM Needs to Know

The PM skill should teach:
1. How to invoke `dispatcher.engine.execute_transition()` for each gate
2. The exact prompt formats for each transition type
3. How to read dispatcher state to check current phase
4. When to use stall detection vs manual intervention
5. Error handling patterns (invalid transitions, missing artifacts)

---

## Phase 4: Entry Points (Gateway Bindings — Optional)

**This step is deferred until requested.** Gateway bindings are entry points only — no workflow logic.

If/when needed:

```json5
// minimal entry-point-only bindings in openclaw.json
{
  "bindings": [
    { agentId: "pm", match: { channel: "webchat", peer: { kind: "command", id: "/eo.task" } } },
    { agentId: "cto", match: { channel: "webchat", peer: { kind: "command", id: "/eo.approve" } } },
    { agentId: "reviewer", match: { channel: "webchat", peer: { kind: "command", id: "/eo.review" } } }
  ]
}
```

---

## Phase 5: Validation & Testing

| Test | Description |
|------|-------------|
| T1 | Valid G0→G1→G2→G3→G4 flow completes without errors |
| T2 | Invalid transition (e.g., G2 directly to G4) is rejected with proper error |
| T3 | Missing artifact blocks transition and reports what's missing |
| T4 | Agent registry checksum mismatch halts transitions and alerts PM |
| T5 | Stall detection fires after idle threshold, creates TASK_STALLED event |
| T6 | State survives gateway restart (read from disk, not in-memory) |
| T7 | Rejection loops (G1→S1, G2→S2, G3→S2, G4→S2) work correctly |
| T8 | Concurrent task handling (two tasks at different phases simultaneously) |

---

## Implementation Priorities

| Priority | Phase | Why |
|----------|-------|-----|
| P0 | 1.1 Registry Loader | Foundation — nothing works without it |
| P1 | 1.2 Workflow Engine | Core state machine |
| P2 | 1.3 State Manager | Persistence |
| P3 | 2.1 Session Dispatch | The "dispatch" in Dispatcher |
| P4 | 3.1 PM Integration | Operational use by PM agent |
| P5 | 4 | Entry points (deferred) |
| P6 | 5 | Validation (parallel with P0-P4) |

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| OpenClaw `sessions_spawn` API changes | Low | Engine wraps the API; adapter pattern makes swaps easy |
| Workflow YAML schema drift | Medium | Validate on load; store checksum per task for audit |
| PM can't self-enforce dispatcher calls | Medium | Tool policy enforces what PM CAN do; dispatcher skill tells PM how to use it |
| Complex rejection loops cause state divergence | Low | All transitions logged immutably in transition_history; state derived from history, not computed on fly |

