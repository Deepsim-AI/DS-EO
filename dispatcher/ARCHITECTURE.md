# DS-EO Dispatcher / Workflow Engine — Architecture

**Version**: 0.1.0  
**Status**: Design  
**Owner**: CTO (architectural), PM (operational)  
**Related**: `dispatcher/DESIGN.md`, `dispatcher/STATE_SCHEMA.md`, `dispatcher/PROTOCOL.md`

---

## Design Philosophy

The Dispatcher is the **single orchestration layer** for DS-EO. It owns:
1. Reading workflow definitions and agent registry
2. Mapping protocol gates (G0–G4) to concrete agent spawns
3. Managing task state lifecycle without external config dependencies

**Key constraint**: Gateway-level bindings only expose entry points (e.g., `/eo task → PM`). All routing logic lives inside DS-EO's dispatcher, not in OpenClaw config.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Entry Points                      │
│  /eo task    ──► PM                                │
│  /eo approve ──► CTO (G1) or PM (G4)              │
│  /eo review  ──► Reviewer                          │
│  user input  ──► CTO (default agent)               │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│              Dispatcher / Workflow Engine            │
│                                                      │
│  dispatcher/                                         │
│  ├── engine.py         ← core state machine          │
│  ├── registry.py       ← agent registry loader       │
│  ├── workflow_defs/    ← workflow definition files   │
│  │   └── default.yaml  ← DS-EO G0-G4 gate machine   │
│  ├── state_manager.py  ← persistent task state       │
│  ├── session_dispatch  ← sessions_spawn/send impl    │
│  └── protocol.py       ← message format + validation │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │   CTO   │ │Implement│ │ Reviewer│
   │  🏗️    │ │  💻     │ │  🔍     │
   └─────────┘ └─────────┘ └─────────┘
        ▲          ▲          ▲
        └──────────┼──────────┘
                   ▼
            ┌─────────────┐
            │     PM      │
            │  📋         │
            └─────────────┘
```

---

## Component Responsibilities

### 1. Agent Registry (`registry.py`)

- Reads `agents_list.json` (the source of truth for available agents)
- Resolves agent IDs to target sessions via OpenClaw's session routing
- Validates that the requesting agent has authority to spawn a target agent
- Refreshes on config change or explicit reload request

### 2. Workflow Engine (`engine.py`)

- Implements the G0-G4 state machine
- Transitions are triggered by gate outcomes (approve, reject, revision)
- Each transition produces a **DispatchEvent** with:
  - `source_agent`: who triggered the transition
  - `target_agent`: where work goes next
  - `event_type`: TASK_OPEN, DELEGATE, IMPL_COMPLETE, REVIEW_COMPLETE, etc.
  - `task_id`: current task context
  - `payload`: structured data for the receiving agent
- Enforces **sequential gate order** — cannot skip gates

### 3. State Manager (`state_manager.py`)

- Persists dispatcher state per task in: `docs/dispatcher/<TASK_ID>/dispatcher_state.json`
- Tracks: current phase (S0-S8 from protocols), last transition timestamp, pending events
- Survives gateway restarts and session resets
- PM reads/writes status; other agents read-only during their turn

### 4. Session Dispatch (`session_dispatch/`)

- Wraps OpenClaw's `sessions_spawn` for agent-to-agent handoffs
- Uses `context="isolated"` for phase-separated sessions (per protocol mandate)
- Maps DS-EO event types to specific spawn parameters:
  - `DELEGATE` → `sessions_spawn(agent="implementer", context="isolated")` with payload in initial prompt
  - `REVIEW_COMPLETE` → `sessions_spawn(agent="reviewer", context="isolated")` with task context
  - etc.

### 5. Protocol (`protocol.py`)

- Defines message/event schemas (already partially in `communication_protocol.md`)
- Validates events before dispatch (required fields, valid states)
- Produces structured prompts for receiving agents

---

## Workflow Definition Format (`workflow_defs/default.yaml`)

Describes the complete G0-G4 gate machine. This is the **single source of truth** for workflow routing logic — it's a data file the engine reads, not code.

```yaml
# workflow_defs/default.yaml
name: ds-eo-standard
version: "1.0"

agents:
  cto:       { model: ollama/qwen3.6:35b,   role: architect }
  implementer: { model: ollama/ornith:35b,  role: coder }
  reviewer:    { model: ollama/laguna-xs-2.1:q4_K_M, role: auditor }
  pm:          { model: ollama/qwen3.6:35b,  role: coordinator }

phases:
  S0_OPEN:     label: "Task Open"        agent: pm       transitions_to: [S1_PLANNING]
  S1_PLANNING: label: "Planning"          agent: cto      transitions_to: [S2_IMPLEMENTATION, S1_PLANNING]
  S2_IMPLEM:   label: "Implementation"    agent: implementer transitions_to: [S3_REVIEW, S2_IMPLEM]
  S3_REVIEW:   label: "Review"            agent: reviewer transitions_to: [S4_APPROVAL, S2_IMPLEMENTATION]
  S4_APPROVAL: label: "Final Approval"    agent: cto      transitions_to: [S5_COMPLETE, S2_IMPLEMENTATION]
  S5_COMPLETE: label: "Complete"           agent: pm       transitions_to: []

transitions:
  # Phase entry
  G0_ENTRY:
    from: null         # external trigger
    to: S0_OPEN
    agent: pm
    event: TASK_OPEN

  # Gate decisions (G1)
  G1_APPROVE:
    from: S1_PLANNING
    to: S2_IMPLEM
    agent: implementer
    event: DELEGATE
    authority: user          # User must approve plan first
    prompt_template: "delegation_prompt"

  G1_REJECT:
    from: S1_PLANNING
    to: S1_PLANNING
    agent: cto
    event: PLAN_REVISED

  # Gate decisions (G2)
  G2_COMPLETE:
    from: S2_IMPLEM
    to: S3_REVIEW
    agent: reviewer
    event: IMPL_COMPLETE
    authority: implementer   # Implementer self-declares
    prompt_template: "review_request"

  G2_INCOMPLETE:
    from: S2_IMPLEM
    to: S2_IMPLEM
    agent: implementer
    event: REVISION_REQUESTED

  # Gate decisions (G3)
  G3_APPROVE:
    from: S3_REVIEW
    to: S4_APPROVAL
    agent: cto
    event: REVIEW_COMPLETE
    authority: reviewer
    prompt_template: "approval_request"

  G3_CHANGES:
    from: S3_REVIEW
    to: S2_IMPLEM
    agent: implementer
    event: REVISION_REQUESTED

  # Gate decisions (G4)
  G4_APPROVE:
    from: S4_APPROVAL
    to: S5_COMPLETE
    agent: pm
    event: PM_CLOSED
    authority: user

  G4_REJECT:
    from: S4_APPROVAL
    to: S2_IMPLEM
    agent: implementer
    event: REVISION_REQUESTED

stall_detection:
  max_phase_duration_minutes: 480  # 8 hours
  idle_threshold_minutes: 120       # 2 hours without artifact update
  action: TASK_STALLED              # PM escalates to CTO
```

---

## State Machine (Phases S0-S5)

```
                    ┌───────┐
              G0_ENTRY │       │ G1_APPROVE
    External ─────────►│  S0   ├──────────────┐
    Trigger           │OPEN   │              ▼
                    └───────┘         ┌───────────────┐
                                    G1_APPROVE│        │G1_REJECT
                                              ▼        │
                                       ┌───────────────▼──┐
                        G2_COMPLETE  │      S1            │
                      ◄──────────────│   PLANNING         │
                  G3_CHANGES     G2_ |                    │
                     ◄──────────┘    |  agent: CTO        │
                  ┌──────────────┐   └────────────────────┘
             G4_APPROVE|          │
                   ◄───│  S5      │
                       │COMPLETE   │  (Post-G4 PM work)
                 ┌─────▼─────┐
           G4_REJECT |        |
              ◄──────│        │
                      └────────┘
                  ┌───────────────┐     ┌───────────────┐
               G3_APPROVE          │    │ S2            │
             ◄─────────────────────┤◄────│  IMPL         │
                     ┌─────────────┘    |              │
                     │                 └───────────────┘
                     ▼
                ┌───────────────┐
                │    S3         │
                │   REVIEW      │
                │  agent: R'vwr │
                └───────────────┘
```

### Rejection Loops (bidirectional arrows)

| From Phase | To Phase | Trigger | Authority |
|-----------|----------|---------|-----------|
| S1_PLANNING | S1_PLANNING | Plan revision needed | User requests changes |
| S2_IMPLEM | S2_IMPLEM | Incomplete implementation | CTO (post-G2) or User |
| S3_REVIEW | S2_IMPLEM | Reviewer requests changes | Reviewer (G3 rejection) |
| S4_APPROVAL | S2_IMPLEM | CTO rejects on G4 | CTO (final authority) |

---

## Entry Points (Gateway Bindings Only)

Gateway-level bindings handle **only** external entry — no workflow logic:

```json5
// In openclaw.json (minimal, non-intrusive)
{
  "bindings": [
    // /eo task → PM starts a new task
    { agentId: "pm", match: { channel: "webchat", peer: { kind: "command", id: "/eo.task" } } },
    // /eo approve (G1) → CTO reviews plan
    { agentId: "cto", match: { channel: "webchat", peer: { kind: "command", id: "/eo.approve" } } },
    // /eo review → Reviewer reviews implementation
    { agentId: "reviewer", match: { channel: "webchat", peer: { kind: "command", id: "/eo.review" } } },
  ]
}
```

No internal routing lives here. It's purely the front door.

---

## Security & Boundaries

- The Dispatcher **cannot create or modify agents** — it reads `agents_list.json` only
- The Dispatcher **cannot change gateway config** — bindings are managed externally
- Agent boundaries are enforced at **two levels**:
  1. Protocol level (what agents agree to)
  2. Tool policy level (gateway enforces allow/deny per agent)
- The dispatcher respects both but never overrides tool policies

---

## Implementation Order

| Step | File | Description |
|------|------|-------------|
| 1 | `workflow_defs/default.yaml` | Workflow definition (data, no code) |
| 2 | `registry.py` | Agent registry loader from agents_list.json |
| 3 | `state_manager.py` | Persistent task state persistence |
| 4 | `protocol.py` | Message/event format validation |
| 5 | `engine.py` | Core state machine + transition logic |
| 6 | `session_dispatch/engine.py` | sessions_spawn wrapper for handoffs |
| 7 | `prompt_templates/` | Prompt templates per transition type |
| 8 | Update PM's agent config to use dispatcher skill | PM orchestrates via dispatcher |
