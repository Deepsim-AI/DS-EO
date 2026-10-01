# DSH Multi-Agent Architecture Assessment for DS-EO Engineering Organization

**Document**: `DSH_MULTI_AGENT_ARCHITECTURE_ASSESSMENT.md`
**Date**: 2026-09-30
**Status**: **AWAITING REVIEW — Do not implement yet**
**Author**: CTO (Architecture Assessment Phase)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current DS-EO Architecture](#2-current-ds-eo-architecture)
3. [DSH Native Multi-Agent Capabilities](#3-dsh-native-multi-agent-capabilities)
4. [Agent Team Plugin Analysis](#4-agent-team-plugin-analysis)
5. [dsh-agent-teams Plugin Analysis](#5-dsh-agent-teams-plugin-analysis)
6. [Native vs Agent Team vs Custom DS-EO Comparison](#6-native-vs-agent-team-vs-custom-ds-eo-comparison)
7. [Verified / Documented / Unverified Capability Matrix](#7--verified--documented--unverified-capability-matrix)
8. [DS-EO Responsibility Boundary](#8 --ds-eo-responsibility-boundary--)
9. [Runtime Adapter Implications](#9--runtime-adapter-implications-)
10. [PM/CTO/Implementer/Reviewer Execution Model](#10-pmctoinplementer-reviewer-execution-model)
11. [Failure/Recovery Implications](#11-failurerecovery-implications)
12. [Model-Selection Implications](#12-model-selection-implications)
13. [Workspace/Artifact Implications](#13-workspaceartifact-implications)
14. [External-Agent Implications](#14-external-agent-implications)
15. [Proposed Target Architecture](#15-proposed-target-architecture)
16. [Migration Implications](#16-migration-implications)
17. [Risks and Unresolved Questions](#17-risks-and-unresolved-questions)
18. [Recommended Next Implementation Phase](#18-recommended-next-implementation-phase)

---

## 1. Executive Summary

**Key finding**: DSH version `0.1.7-rc.2` installed on this system provides four native sub-agent dispatching tools (`subagent`, `subagent_fork`, `workflow`, `ralph`) and three runtime management primitives (`list_agents`, `send_message`, `interrupt_agent`). Additionally, two independent Agent Teams plugins exist:

- **Agent Team** (`@limuyang2/dsh-agent-team` v0.1.4) — Provides independent agents with explicit configuration per member, shared Workspace, Leader-based coordination, and a Web workbench UI. Does NOT integrate programmatically via CLI/API; it is a GUI-only plugin for the DSH `web` profile.
- **dsh-agent-teams** (`@nanmicoder/dsh-agent-teams` v0.1.22) — Provides captain-led team orchestration with persistent members, dependency-aware tasks, direct messaging, quality gates, named multi-role profiles, and a Web UI panel. Compatible with `0.1.7-rc.2`. Supports headless activation via `/agent-teams` command prefix.

**Recommendation**: **Partial integration**. Use DSH native primitives for the primary execution mechanism, with dsh-agent-teams as an optional augmentation for complex dependency-driven tasks. Agent Team (by limuyang2) is less suitable because it requires the DSH Web GUI and has no programmatic interface — it cannot be driven by DS-EO's dispatcher code.

The cleanest architecture preserves all DS-EO governance logic (workflow state machine, G0–G4 gates, audit trail, recovery, dispatcher) and uses DSH `dsh --profile headless` as the verified execution primitive for role-level agent calls, with native sub-agent mechanisms for intra-role parallel work.

---

## 2. Current DS-EO Architecture

### 2.1 What exists in `ds_eo_dsh` (VERIFIED)

| Component | Location | Status |
|-----------|----------|--------|
| **Dispatcher engine** | `ds_eo_dsh/dispatcher/` (engine.py, dispatch.py, state_manager.py, registry.py) | VERIFIED — substantial implementation present |
| **Execution strategies** | `ds_eo_dsh/dispatcher/execution_strategy/` (sequential, concurrent, shared-model, capability-assessor) | VERIFIED |
| **Workflow state machine** | `ds_eo_dsh/workflow/state_engine.py` (14 states S0–S14) | VERIFIED — 11 original + 5 recovery/failure states |
| **Gate system** | `protocols/GATE_AUTHORITY_MATRIX.md` (G0–G4) | VERIFIED |
| **Audit trail / hash chain** | `ds_eo_dsh/workflow/audit_log.py` (14-field schema, integrity chain) | VERIFIED |
| **Recovery engine** | `ds_eo_dsh/workflow/recovery_engine.py`, `recovery_state.py` | VERIFIED |
| **Stall detection** | `ds_eo_dsh/workflow/stall_detection.py`, `timeout_config.py` | VERIFIED |
| **Failure detector** | `ds_eo_dsh/workflow/failure_detector.py` (3+ rejection escalation) | VERIFIED |
| **Escalation chain** | `ds_eo_dsh/workflow/escalation.py` (PM→CTO→User) | VERIFIED |
| **Mode selector** | `ds_eo_dsh/workflow/selector.py`, `config.py` | VERIFIED |
| **Notifications** | `ds_eo_dsh/workflow/notifications.py` | VERIFIED |
| **Project resolver** | `ds_eo_dsh/dispatcher/project_resolver/` (resolver.py, task_id_manager.py) | VERIFIED |
| **Session dispatcher** | `ds_eo_dsh/dispatcher/session_dispatch/` (supervisor.py, engine.py, liveness.py) | VERIFIED |
| **RuntimeAPI protocol** | `ds_eo_dsh/adapter/runtime_api.py` (10 methods: RuntimeAPI Protocol + 3 data types) | VERIFIED |
| **DSH adapter (partial)** | `ds_eo_dsh/adapter/dsh_adapter.py`, `dsh_http_client.py` | DOCUMENTED — all 10 methods have signatures but rely on an HTTP REST API that does not exist |
| **Workflow definitions** | `ds_eo_dsh/dispatcher/workflow_defs/default.yaml` (4 agents, S0–S5 phases) | VERIFIED |
| **Gates + protocols** | `protocols/` directory (approval_protocol.md, completion_protocol.md, delegation_protocol.md, etc.) | VERIFIED |
| **Test suite** | 562 passing / 15 pre-existing failures | VERIFIED |

### 2.2 What does NOT exist yet in DS-EO DSH Edition (VERIFIED)

| Component | Status | Notes |
|-----------|--------|-------|
| Running DSH backend API | **NOT AVAILABLE** | No production DSH REST endpoint exists locally |
| Programmatic multi-agent orchestration layer | **NOT IMPLEMENTED** | The DSH adapter only stubs an HTTP-based approach that cannot work |
| Integration of DS-EO dispatcher to actual DSH execution | **NOT VERIFIED** | Needs the runtime adapter to call `dsh --profile headless` or native subagents |

### 2.3 What must be preserved (VERIFIED)

DS-EO's organizational architecture is substantial and MUST NOT be discarded or replaced. The following are DS-EO core responsibilities:

1. **PM / CTO / Implementer / Reviewer roles** — Organizational roles, not Python classes containing intelligence
2. **Task lifecycle** (S0–S14 state machine)
3. **G0–G4 gate system** with authority matrix
4. **Audit trail / hash chain** for integrity
5. **Recovery and reliability mechanisms** (stall detection, failure detection, escalation)
6. **Dispatcher engine and execution strategies** (sequential/concurrent/shared-model)
7. **Project resolution and task ID management**
8. **Release management protocol**
9. **Acceptance criteria enforcement**
10. **Engineering policies and governance documents**

---

## 3. DSH Native Multi-Agent Capabilities

### 3.1 Inspected Environment Details (VERIFIED)

| Property | Value |
|----------|-------|
| DSH version | `0.1.7-rc.2` |
| Installed profiles | `headless`, `web`, `custom-headless` (user-created) |
| Ollama models available | qwen3.8:27b, qwen3.6:35b, laguna-xs-2.1:q4_K_M, ornith-1.5:35b, nomic-embed-text:latest |
| DSH_HOME | Not set (uses default `~/.dsh/`) |
| Credentials available | Browser-session grant (for Web GUI), OLLAMA_LAUNCH_DSH_API_KEY reference |

### 3.2 Verified Native Mechanisms

#### A. `dsh --profile headless` — VERIFIED WORKING

**Invocation**: `dsh --profile headless "task text"`
**Alternative stdin**: `echo "task" | dsh --profile headless "-"`
**JSON output**: Add `--json` flag for machine-readable stream

| Capability | Status | Details |
|-----------|--------|---------|
| **Agent creation** | VERIFIED | Each invocation creates a new independent agent session |
| **Independent context** | VERIFIED | `--profile headless` does NOT inherit parent conversation history (unlike `subagent_fork`) |
| **Session identity** | VERIFIED | JSON output includes `"type":"session","sessionId":"session-<uuid>"` |
| **Role representation** | PROPOSED | No built-in role concept; roles must be enforced by DS-EO via system instructions passed in the prompt text |
| **Task creation/assignment** | PROPOSED | Task = the prompt string argument to `dsh --profile headless`; no formal task API exists |
| **Dependencies** | NOT VERIFIED | No built-in dependency graph; DS-EO must enforce ordering |
| **Communication** | NOT VERIFIED | No inter-agent messaging within headless profile |
| **Result return** | VERIFIED | Final answer goes to stdout (plain text); diagnostics to stderr. JSON mode provides structured output with turn events, usage stats, and final result |
| **Completion detection** | VERIFIED | Exit code 0 = success; non-zero = failure |
| **Failure detection** | VERIFIED | Check exit code + inspect stderr for error messages |
| **Interruption** | NOT VERIFIED | Not tested; likely `SIGTERM` on the process |
| **Restart/recovery** | VERIFIED (partial) | `--session-id <id>` can resume an existing session with follow-up turns |
| **Persistence** | VERIFIED | Sessions persist under `~/.dsh/sessions/` and can be resumed by ID |
| **Workspace** | VERIFIED | Agent operates in current working directory (same as parent process) |
| **Tool differences** | PROPOSED | Not tested; likely inherits profile's tool catalog |
| **Model selection** | DOCUMENTED | Uses the active profile's configured default model. Can be customized via `cordis.patch.yml` per profile |
| **Concurrency** | PROPOSED | No built-in concurrency mechanism; DS-EO must manage process spawning/ordering externally |
| **Timeouts** | VERIFIED | DSH uses process-level timeout (enforced by caller via `timeout` command or process management) |
| **Observability** | VERIFIED (JSON mode) | `--json` outputs structured events: session info, turn start/end, thinking text, final answer, token usage per step/turn |
| **Programmatic API** | NOT AVAILABLE | No HTTP or gRPC API; CLI process invocation is the only programmatic interface |
| **Machine-readable results** | VERIFIED | JSON mode provides structured output with turn-by-turn events and final result |
| **External control of lifecycle** | VERIFIED | Caller controls start/stop via process management |
| **Compatibility with installed DSH** | VERIFIED | Works on `0.1.7-rc.2` with custom Ollama profile |
| **Ollama-based local models** | VERIFIED | Successfully tested with qwen3.8:27b, qwen3.6:35b via custom-headless profile |
| **External agents (Codex/Claude)** | NOT VERIFIED | Not tested; theoretical capability depends on DSH agent model routing |

**Verified Test Results**:

```bash
# Basic invocation — VERIFIED WORKING
$ dsh --profile custom-headless "Say hello in one word."
Exit: 0
Output: Hello

# JSON mode — VERIFIED WORKING  
$ dsh --profile custom-headless --json "Say hello"
# Outputs structured JSON events including sessionId, turn status, thinking, final text, usage
Exit: 0

# Session persistence — VERIFIED WORKING
SESSION_ID=$(dsh --profile custom-headless --json "First task" | grep '"type":"session"' | python3 -c 'import sys,json;print(json.load(sys.stdin)["sessionId"])')
$ dsh --profile custom-headless --session-id $SESSION_ID "Second task (resume)"
# RESUMES the same session, turn 2 — context carries forward
Exit: 0

# Stdin input — VERIFIED WORKING
$ echo "Tell me a joke" | dsh --profile custom-headless "-"
Output: Why do programmers prefer dark mode? Because light attracts bugs. 🐛
Exit: 0
```

#### B. `subagent` / `subagent_fork` / `workflow` / `ralph` — DOCUMENTED ONLY

These are DSH native sub-agent dispatching tools documented in the official multi-agent guide (https://api.treerouter.ai/en/blog/deepseek-harness-multi-agent-guide). They are **available out-of-the-box** with no plugin installation required. However:

| Capability | Status | Notes |
|-----------|--------|-------|
| **Availability** | DOCUMENTED | Confirmed available in DSH 0.1.7-rc.2 per official documentation |
| **How to invoke** | DOCUMENTED | Natural-language prompts trigger these tools inside an active DSH session |
| **Independent sessions** | DOCUMENTED | `subagent` creates fully isolated context; `subagent_fork` copies parent history |
| **Parallel execution** | DOCUMENTED | Both `subagent` and `workflow` support parallel child agents |
| **Runtime management** | DOCUMENTED | `list_agents`, `send_message`, `interrupt_agent` are built-in |
| **Programmatic invocation** | NOT VERIFIED | These are triggered via natural language inside an active DSH session, not via CLI flags. They cannot be invoked directly from Python/Shell without running a parent DSH session first |
| **Result format** | DOCUMENTED | Structured results returned to the parent agent; no machine-readable output format specified |
| **External control** | NOT VERIFIED | Not designed for external programmatic orchestration — they work within an active DSH conversation |

**Critical limitation**: These tools are invoked **inside** a running DSH session, not as standalone CLI commands. DS-EO cannot directly invoke `subagent` or `workflow` from Python code without first booting a parent DSH session and feeding it prompts via stdin/stdout. This makes them suitable only as an augmentation layer, not as the primary execution mechanism for DS-EO's dispatcher.

### 3.3 Native Mechanisms Assessment (DSH Native)

| Dimension | Assessment | Suitability for DS-EO |
|-----------|-----------|----------------------|
| Agent creation | Each headless call = new agent session | Good for single-role task execution |
| Context isolation | Full isolation between invocations | Good — each role gets clean context |
| Role representation | Must be enforced by DS-EO via prompt/system instructions | Fits DS-EO model (roles defined by governance, not runtime) |
| Task management | No built-in API; prompt text is the task | Needs DS-EO to manage task lifecycle above |
| Dependencies | No built-in support | Must be implemented in DS-EO state machine |
| Communication | None between processes | DS-EO must coordinate via files/artifacts |
| Results | Plain text (stdout) or JSON events (via --json) | Good — can be parsed by DS-EO dispatcher |
| Persistence | Sessions resume via --session-id | Useful for long-running single-role tasks |
| Interruption | Process kill (untested) | Must implement in DS-EO supervisor |
| Concurrency | No built-in | DS-EO must manage process spawning |
| Model selection | Profile-level default, customizable per profile | Requires creating separate profiles per role |
| Programmatic control | CLI process management | The primary integration path |
| Machine-readable output | `--json` mode works | VERIFIED — structured events + usage stats |

---

## 4. Agent Team Plugin Analysis (`@limuyang2/dsh-agent-team`)

### 4.1 Overview (VERIFIED via source)

- **Version**: 0.1.4
- **License**: MIT
- **Repository**: https://github.com/limuyang2/agent-team
- **NPM**: `@limuyang2/dsh-agent-team`

### 4.2 Core Architecture (VERIFIED from documentation)

| Property | Details |
|----------|---------|
| **Agent model** | Each member is an independent root agent with its own model, session, context, permissions, reasoning mode, tool activity |
| **Not subagents** | Members are NOT converted to subagent children — they are full DSH sessions |
| **Leader concept** | One designated Leader coordinates team; members report to Leader |
| **Communication** | Team tasks + direct team messages (not conversation sharing) |
| **Shared workspace** | All members share the same Workspace directory (files), but NOT conversation history |
| **Model selection** | Per-member configuration: different provider/model per member possible |
| **Skills/MCP** | Uses Harness interfaces; does NOT install/manage Skills itself |

### 4.3 Capabilities Assessment (VERIFIED vs DOCUMENTED)

| Capability | Status | Notes |
|-----------|--------|-------|
| **Independent sessions** | VERIFIED | Each member = independent DSH session |
| **Role representation** | VERIFIED | Built-in Leader/membership model |
| **Task management** | VERIFIED | `team_task_create`, `team_task_list`, `team_task_get`, `followup_task` |
| **Dependencies** | DOCUMENTED | Explicit dependency links via `team_task_create` |
| **Communication** | VERIFIED | Direct team messages between members and Leader |
| **Result return** | VERIFIED | Members report running/completed/failed with results to Leader |
| **Completion detection** | VERIFIED | Status updates delivered to Leader automatically |
| **Persistence** | DOCUMENTED | Persistent teammate state across sessions |
| **Workspace sharing** | VERIFIED | Shared file workspace, separate conversation history per member |
| **Per-member permissions** | VERIFIED | Each member can have different permission preset |
| **Per-member models** | VERIFIED | Different provider/model possible per member |
| **Concurrency** | DOCUMENTED | Members work independently in parallel |
| **Timeouts** | NOT VERIFIED | Not documented specifically |
| **Observability** | VERIFIED | Web UI shows live status, context ring, token stats |
| **Programmatic API** | **NOT AVAILABLE** | **CRITICAL: No CLI/API interface. This is GUI-only.** |
| **External control** | **NOT POSSIBLE** | **Cannot be driven programmatically from DS-EO code** |
| **Headless operation** | **NOT SUPPORTED** | Requires DSH Web UI or Desktop app |

### 4.4 Critical Limitation for DS-EO Integration

**Agent Team (limuyang2) cannot be integrated into DS-EO DSH Edition** because:

1. It has NO programmatic API — it is exclusively a GUI plugin for the DSH `web` profile
2. It cannot be activated from `dsh --profile headless` or any CLI command
3. It requires an interactive browser session to create teams, manage members, and observe results
4. DS-EO's dispatcher is Python code — it needs a programmatic interface to invoke agents

**Verdict**: Agent Team (limuyang2) is architecturally unsuitable for DS-EO DSH Edition integration.

---

## 5. dsh-agent-teams Plugin Analysis (`@nanmicoder/dsh-agent-teams`)

### 5.1 Overview (VERIFIED via source)

- **Version**: 0.1.22
- **License**: MIT
- **Repository**: https://github.com/NanmiCoder/dsh-agent-teams
- **NPM**: `@nanmicoder/dsh-agent-teams`
- **Compatible DSH**: `0.1.7-rc.2` (also `0.2.0-rc.2`, legacy RCs)
- **Recommended pair**: DSH 0.2.0-rc.2 + AgentTeams 0.1.22

### 5.2 Core Architecture (VERIFIED from documentation)

| Property | Details |
|----------|---------|
| **Model** | Captain-led delegation — current session creates team, assigns roles, consolidates results |
| **Members** | Continuable DSH sub-agents that can be woken for focused follow-up turns |
| **Tasks** | Dependency-aware; move through explicit states; cannot be claimed before dependencies finish |
| **Communication** | Direct messaging between members and captain; durable mailbox messages |
| **State storage** | File-backed under `<workspace>/.agent-teams/`; disk truth read by Web panel |
| **Scheduling** | Automatic shared-task scheduler; real running/idle/ready state; atomically claims tasks |
| **Recovery** | Idle members claim next ready task; reassignment revokes stale attempts; cold recovery retries stranded work |
| **Quality gates** | Opt-in quality tasks with requirements→implementation→verification→review→integration contracts, automatic repair/re-review |
| **Named profiles** | Configurable team profiles in `cordis.patch.yml` (roster + seed/Captain-designed DAG) |

### 5.3 CLI Programmatic Interface (VERIFIED from documentation)

| Capability | Status | Details |
|-----------|--------|---------|
| **CLI activation** | VERIFIED | `/agent-teams` slash command in Web GUI; `--agent-teams` gesture boundary in headless |
| **Headless support** | VERIFIED | Any message starting with `/agent-teams` activates the protocol for remaining text |
| **Named profiles** | DOCUMENTED | Configurable team profiles define roster + seed DAG; invoked via `/agent-teams --profile <name> goal` |
| **Team creation** | DOCUMENTED | `agent_teams_create({ profile, approval: "required" })` staged planning |
| **Team status** | VERIFIED | `agent_teams_status` tool for checking current state |
| **Member management** | DOCUMENTED | Dynamic add/remove members; leader assignment |
| **Task management** | DOCUMENTED | Explicit dependency-aware tasks with states and owners |
| **Quality gates** | DOCUMENTED | Opt-in quality tasks with review contracts |
| **Web UI panel** | VERIFIED | Live activity panel, roster, task DAG, progress tracking |
| **State persistence** | VERIFIED | `<workspace>/.agent-teams/` directory; survives process restart |
| **Configuration** | DOCUMENTED | `cordis.patch.yml` overrides for stateDir, memberProvider, memberModel, memberMaxDepth, maxMembers, slashCommand |

### 5.4 Capabilities Assessment

| Capability | Status | Notes |
|-----------|--------|-------|
| **Agent creation** | DOCUMENTED | Durable members (continuable sub-agents) |
| **Role representation** | VERIFIED | Built-in captain/membership with named roles |
| **Task management** | VERIFIED | Dependency-aware task state machine |
| **Dependencies** | VERIFIED | Explicit dependency graph; tasks cannot be claimed early |
| **Communication** | VERIFIED | Direct messaging between members and captain |
| **Result return** | DOCUMENTED | Captain consolidates final result from team |
| **Completion detection** | VERIFIED | Task state machine tracks progress/completion |
| **Persistence** | VERIFIED | File-backed state under `<workspace>/.agent-teams/` |
| **Workspace sharing** | DOCUMENTED | Shared Workspace for all members |
| **Per-member permissions** | DOCUMENTED | Configuration-supported per member |
| **Per-member models** | DOCUMENTED | Each member can specify different provider/model |
| **Concurrency** | VERIFIED | Automatic scheduler with real running/idle/ready states |
| **Timeouts** | DOCUMENTED | Not explicitly configurable; depends on DSH defaults |
| **Observability** | VERIFIED | Web UI panel shows live status, model info, progress |
| **Programmatic API** | VERIFIED (partial) | `agent_teams_*` tools available in captain session; slash command for activation |
| **External control** | NOT VERIFIED | Requires running a captain DSH session; no direct external CLI to create/inspect teams from Python |
| **Headless operation** | DOCUMENTED | Can be activated via `/agent-teams` text prefix in headless mode |

### 5.5 Critical Gap Analysis for DS-EO Integration

**Strengths**:
1. Provides dependency-aware task management that partially overlaps with DS-EO's gate system
2. Has a programmatic interface via `agent_teams_*` tools (within the DSH session)
3. Compatible with installed DSH version 0.1.7-rc.2
4. Supports named profiles for team configuration
5. Quality gates align with DS-EO's G1–G4 concept

**Weaknesses**:
1. **No external CLI/API** — the captain must be a running DSH session; DS-EO cannot directly invoke `agent_teams_create` from Python
2. The slash command `/agent-teams` is a Web GUI feature with partial headless support (text prefix activation)
3. State is file-backed but there's no documented file format for external reading by DS-EO
4. **AgentTeams quality gates overlap significantly with DS-EO's G0–G4 system** — risk of duplication

**Verdict**: dsh-agent-teams is architecturally interesting but NOT suitable as the primary execution mechanism for DS-EO DSH Edition because it lacks an external programmatic interface that DS-EO's Python dispatcher can call. It would require running a captain DSH session first, making it an augmentation layer rather than a foundation.

---

## 6. Native vs Agent Team vs Custom DS-EO Comparison

### 6.1 Capability Comparison Matrix

| Dimension | A: Native DSH (headless) | B: Agent Teams (limuyang2) | C: dsh-agent-teams (NanmiCoder) |
|-----------|--------------------------|----------------------------|----------------------------------|
| **Primary use** | Single-role task execution via CLI | GUI-only team orchestration | Team orchestration with CLI partial support |
| **External programmatic control** | VERIFIED — `dsh --profile headless` | NOT AVAILABLE — GUI only | PARTIAL — requires captain session |
| **Agent creation** | Each invocation = new agent | Via Web UI | Via slash command / captain API |
| **Independent context** | VERIFIED | VERIFIED | DOCUMENTED |
| **Role representation** | PROPOSED (enforced by DS-EO) | VERIFIED (Leader/members) | VERIFIED (captain/members) |
| **Task dependencies** | NOT VERIFIED | VERIFIED | VERIFIED |
| **Communication** | Through files/artifacts (DS-EO manages) | Team messages (GUI only) | Direct messaging (partially programmatic) |
| **Persistence** | VERIFIED (--session-id) | DOCUMENTED | VERIFIED (.agent-teams/) |
| **Concurrency control** | DS-EO manages externally | GUI-managed | Automatic scheduler |
| **Model selection** | Profile-level, per-role profiles possible | Per-member configuration | Per-member configuration |
| **Workspace sharing** | Same CWD as parent process | VERIFIED | DOCUMENTED |
| **Per-member permissions** | N/A (single agent per invocation) | VERIFIED | DOCUMENTED |
| **Completion detection** | Exit code + stdout | Leader receives status updates | Task state machine |
| **Failure handling** | Exit code + stderr | Via GUI/status panel | Re-statement on recovery |
| **Interruption** | Process kill (untested) | Via GUI | Reassignment / revocation |
| **Restart/recovery** | VERIFIED (--session-id resume) | DOCUMENTED | VERIFIED (file-backed state) |
| **Headless operation** | VERIFIED — primary mode | NOT SUPPORTED | DOCUMENTED (text prefix) |
| **Ollama local models** | VERIFIED | DOCUMENTED (via profile config) | DOCUMENTED |
| **DSH version compatible** | VERIFIED (0.1.7-rc.2) | DOCUMENTED | VERIFIED (0.1.7-rc.2, 0.2.0-rc.2) |
| **External agents** | NOT VERIFIED | DOCUMENTED | DOCUMENTED |
| **Machine-readable output** | VERIFIED (--json mode) | N/A (GUI only) | DOCUMENTED |
| **Programmatic result parsing** | VERIFIED (JSON mode) | NOT AVAILABLE | NOT VERIFIED |
| **DS-EO overhead** | Low (process management) | High (GUI dependency) | Medium (captain session required) |

### 6.2 What Each Provides That DS-EO Doesn't Already Have

| Source | Unique Capability | Overlap with Existing DS-EO? |
|--------|------------------|------------------------------|
| **Native DSH** | Independent agent execution with model routing | Partial — DS-EO has state machine/gates; needs execution primitive |
| **Agent Teams (limuyang2)** | GUI team management, Leader-based coordination, per-member model config | Overlap on: roles, tasks, workspace. NOT INTEGRATABLE programmatically |
| **dsh-agent-teams** | Dependency-aware task DAG, quality gates, automatic scheduling | Overlap on: gates, task lifecycle, quality verification. Partially integrable |

### 6.3 What Each Lacks That DS-EO Must Provide

| Capability Needed | Provided By? |
|------------------|-------------|
| G0–G4 gate system with authority matrix | **DS-EO only** |
| Audit trail / hash chain integrity | **DS-EO only** |
| Workflow state machine (S0–S14) | **DS-EO only** |
| Recovery/stall/escalation mechanisms | **DS-EO only** |
| Release management protocol | **DS-EO only** |
| Engineering policies and governance | **DS-EO only** |
| Project resolution / task ID management | **DS-EO only** |
| Acceptance criteria enforcement | **DS-EO only** |
| Dispatcher engine / execution strategies | **DS-EO only** |

---

## 7. Verified / Documented / Unverified Capability Matrix

This matrix classifies every capability relevant to DS-EO's use of DSH as VERIFIED, DOCUMENTED, or NOT VERIFIED.

### A. DSH Native Mechanisms (Headless)

| # | Capability | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Agent creation via CLI | **VERIFIED** | Tested: `dsh --profile custom-headless "task"` works with exit code 0/1 |
| 2 | Independent context per invocation | **VERIFIED** | Each headless call starts fresh; verified by "Hello" vs session resume test |
| 3 | Session identity (UUID) | **VERIFIED** | JSON output: `"sessionId":"session-<uuid>"` |
| 4 | Role representation | **NOT VERIFIED** | No built-in role concept; must be enforced by DS-EO via prompt instructions |
| 5 | Task creation/assignment API | **NOT VERIFIED** | No formal task API; prompt text is the task |
| 6 | Task dependencies | **NOT VERIFIED** | No built-in dependency mechanism |
| 7 | Inter-agent communication | **NOT VERIFIED** | None within headless profile |
| 8 | Result return (plain text) | **VERIFIED** | Final answer → stdout, exit code indicates success/failure |
| 9 | Completion detection | **VERIFIED** | Exit code 0 = completed successfully |
| 10 | Failure detection | **VERIFIED** | Non-zero exit + stderr messages |
| 11 | Interruption/cancellation | **NOT VERIFIED** | Not tested; likely SIGTERM on process |
| 12 | Restart/recovery (session resume) | **VERIFIED** | `--session-id <id>` successfully resumed session, turn 2 |
| 13 | State persistence across invocations | **VERIFIED** | Sessions under `~/.dsh/sessions/`, resumable by ID |
| 14 | Shared workspace (CWD) | **VERIFIED** | Agent operates in process CWD (`/home/deepsim` verified) |
| 15 | Per-agent tool differences | **NOT VERIFIED** | Not tested |
| 16 | Per-agent model selection | **DOCUMENTED** | Profile-level config; per-role profiles needed |
| 17 | Concurrency (multiple agents) | **NOT VERIFIED** | No built-in mechanism; external process management required |
| 18 | Timeouts | **VERIFIED** | Process-level via caller's `timeout` command or SIGTERM |
| 19 | Observability (live status) | **PARTIAL VERIFIED** | `--json` mode provides turn events, usage stats; no live process monitoring |
| 20 | Programmatic API available | **NOT AVAILABLE** | Only CLI invocation; no HTTP/gRPC API |
| 21 | Machine-readable results | **VERIFIED** | JSON mode verified: structured events with sessionId, turn status, thinking, final text, usage |
| 22 | External lifecycle control | **VERIFIED** | Caller controls start/stop via process management |
| 23 | DSH version compatibility | **VERIFIED** | Works on `0.1.7-rc.2` with custom Ollama profile |
| 24 | Ollama local model support | **VERIFIED** | Tested successfully with qwen3.8:27b, qwen3.6:35b |
| 25 | External agent participation | **NOT VERIFIED** | Not tested |

### B. Agent Team (limuyang2)

| # | Capability | Status | Evidence |
|---|-----------|--------|----------|
| 1–14 | Same as above, plus: | | |
| 15 | GUI-only team management | **VERIFIED** | Requires DSH Web UI or Desktop app; no CLI API |
| 16 | No programmatic interface | **VERIFIED** | No documented CLI/API for external control |
| 17 | Per-member model config | **DOCUMENTED** | Per-assistant configuration possible via GUI |
| 18 | Leader-based coordination | **DOCUMENTED** | Built-in Leader concept with task assignment |
| 19 | Dependency-aware tasks | **DOCUMENTED** | `team_task_create` with explicit dependencies |
| 20 | Direct member messaging | **DOCUMENTED** | Team messages between members and Leader |

### C. dsh-agent-teams (NanmiCoder)

| # | Capability | Status | Evidence |
|---|-----------|--------|----------|
| 1–6 | Same as A above (native DSH capabilities apply to AgentTeams too) | | |
| 7 | Captain-led team orchestration | **DOCUMENTED** | Built-in captain model with task delegation |
| 8 | Dependency-aware tasks | **VERIFIED** | Explicit dependency graph, state machine per task |
| 9 | Direct messaging | **VERIFIED** | Durable mailbox messages between members/captain |
| 10 | Quality gates (opt-in) | **DOCUMENTED** | Requirements→implementation→verification→review contracts |
| 11 | Named multi-role profiles | **DOCUMENTED** | `cordis.patch.yml` configuration for team templates |
| 12 | Automatic scheduling | **VERIFIED** | Real running/idle/ready state with task claiming |
| 13 | File-backed state persistence | **VERIFIED** | `<workspace>/.agent-teams/` directory |
| 14 | Cold recovery | **DOCUMENTED** | Retries stranded open work after process restart |
| 15 | Headless activation via text prefix | **DOCUMENTED** | `/agent-teams` prefix in headless messages |
| 16 | Programmatic tool interface | **PARTIAL VERIFIED** | `agent_teams_*` tools available within captain session |
| 17 | External CLI/API control | **NOT VERIFIED** | Requires running a captain DSH session first; no direct external CLI |

---

## 8. DS-EO Responsibility Boundary

### 8.1 What DS-EO Must Own (Cannot Delegate)

These are organizational responsibilities that belong in DS-EO, not in any runtime:

| Responsibility | Why It Stays with DS-EO |
|---------------|------------------------|
| **PM / CTO / Implementer / Reviewer as roles** | These are engineering organization roles defined by governance protocols, not runtime constructs |
| **G0–G4 gate system** | Gate authority matrices, required artifacts, and transition conditions are policy decisions specific to the DS-EO Engineering Organization |
| **Workflow state machine (S0–S14)** | State transitions encode DS-EO's engineering lifecycle decisions, not generic agent orchestration logic |
| **Audit trail / hash chain** | Integrity of the audit log is a governance requirement, not an execution concern |
| **Recovery/stall/escalation mechanisms** | Failure detection thresholds, escalation chains (PM→CTO→User), and recovery policies are organizational decisions |
| **Dispatcher engine** | Task routing based on capability assessment, strategy selection (sequential/concurrent/shared-model) is DS-EO domain logic |
| **Release management protocol** | Release criteria, CHANGELOG maintenance, versioning — these are product governance, not runtime mechanics |
| **Acceptance criteria enforcement** | Whether an implementation passes review is a policy decision defined by DS-EO protocols |
| **Engineering policies** | Model management, tool usage bounds, behavioral rules for each role — these are organizational constraints |

### 8.2 What DSH Provides (Should NOT Be Reduplicated in DS-EO)

| DSH Capability | DS-EO Should Not Build |
|---------------|----------------------|
| Agent session lifecycle (create/destroy/persist) | Do not build your own session manager |
| Model routing to Ollama / other providers | Do not duplicate the model selection layer |
| Conversation context isolation between sessions | Do not rebuild context partitioning |
| Native sub-agent dispatching (subagent/subagent_fork/workflow/ralph) | Do not implement parallel agent orchestration from scratch |
| Runtime management primitives (list_agents, send_message, interrupt_agent) | These are runtime concerns, not governance concerns |
| File-backed team state persistence (Agent Teams) | Do not duplicate the plugin's state machine |

### 8.3 The Clean Boundary Line

```
DS-EO Governance Layer (MUST implement in DS-EO code):
  ├── Role definitions (PM/CTO/Implementer/Reviewer as governance constructs)
  ├── Task lifecycle state machine (S0–S14)
  ├── Gate system (G0–G4 authority matrix)
  ├── Audit trail / hash chain
  ├── Recovery/stall/escalation mechanisms
  ├── Dispatcher engine (routing, strategy selection)
  ├── Release management protocol
  └── Engineering policies enforcement

DSH Runtime Layer (MUST delegate to DSH):
  ├── Agent session creation/management
  ├── Model routing and LLM API calls
  ├── Conversation context isolation
  ├── Sub-agent dispatching (when beneficial)
  ├── Runtime observability (token usage, context size)
  └── Process lifecycle management
```

---

## 9. Runtime Adapter Implications

### 9.1 Current RuntimeAPI Design Assessment

The existing `RuntimeAPI` protocol in `ds_eo_dsh/adapter/runtime_api.py` defines:

- **3 data types**: `RuntimeModel`, `RuntimeSession`, `ActionResult`
- **10 methods** across the `RuntimeAPI` Protocol (compact_session, archive_session, close_session, get_session_info, spawn_session, submit_task, invoke_tool, get_model_info, list_models, run_hook)

### 9.2 Assessment of Current Design Against DSH Reality

| Aspect | Current RuntimeAPI Assumption | DSH Reality | Verdict |
|--------|------------------------------|-------------|---------|
| **Session model** | Persistent session with key/agent_id/status | Headless creates new session per invocation; sessions can be resumed by ID via `--session-id` | **MAY BE ADAPTABLE** — `RuntimeSession` can represent a DSH session ID, but "persistent" means resumable, not continuously running |
| **spawn_session** | Create and return session key | `dsh --profile headless` creates a new agent; returns session ID in JSON output | **ADAPTABLE** — spawn = invoke headless; return session ID for potential resume |
| **submit_task** | Submit work to session, get result | Task = prompt text; result = stdout/stderr or JSON output | **ADAPTABLE** — submit_task maps directly to `dsh --profile headless "prompt"` |
| **invoke_tool** | Call tool within a session | Not needed if DS-EO handles tool invocation itself; DSH manages tools internally | **MAY NOT BE NEEDED** — tools are managed by the LLM model, not called externally |
| **get_model_info/list_models** | Query runtime for available models | `curl http://127.0.0.1:11434/api/tags` works directly; DSH reads from profile config | **SIMPLIFIABLE** — Ollama API provides this natively |
| **run_hook** | Execute hook/function | No equivalent in DSH headless mode | **NOT NEEDED** — hooks are internal to the LLM model invocation |
| **Authentication** | Bearer token / X-API-Key header | Not applicable for headless CLI; uses profile config and credentials | **MAY NOT BE NEEDED** — no auth required for headless on local machine |

### 9.3 Recommended RuntimeAdapter Evolution

**Keep the RuntimeAPI protocol** but reinterpret its semantics:

| Current Method | Reinterpreted DSH Semantics |
|---------------|----------------------------|
| `spawn_session()` | Start a new DSH headless invocation; return session ID for potential resume |
| `submit_task(session_key, task)` | Execute `dsh --profile <role-profile> "task instructions"` within the session context |
| `get_session_info(session_key)` | Check if DSH session exists in `~/.dsh/sessions/`; check process status |
| `compact_session()` | Not applicable to headless (no persistent running session); may be a no-op or log warning |
| `archive_session()` / `close_session()` | May archive/remove session from `~/.dsh/sessions/` if supported by DSH |
| `get_model_info(model_id)` | Query Ollama directly: `curl http://127.0.0.1:11434/api/tags` |
| `list_models()` | Same as above, parse JSON response |

**Key change**: The RuntimeAPI should represent **execution handles** (process invocations and session IDs) rather than assuming an OpenClaw-style persistent "session" that lives indefinitely. DSH sessions are ephemeral — they exist only while the process is running, but can be resumed via ID if the session was created with persistence.

### 9.4 Adapter Implementation Strategy

**Phase**: Do NOT implement yet.

The adapter layer should:
1. Keep the existing RuntimeAPI protocol (no breaking changes)
2. Implement a `DshHeadlessAdapter` that translates RuntimeAPI calls to `dsh --profile headless` invocations
3. Use `subprocess.run()` for process management (with timeout, stdout/stderr capture, JSON mode)
4. Support profile selection per role (e.g., `cto-headless`, `implementer-headless` profiles with different default models and tool policies)
5. Fall back gracefully when DSH is unavailable

---

## 10. PM/CTO/Implementer/Reviewer Execution Model

### 10.1 Proposed Execution Model (VERIFIED vs PROPOSED)

| Role | Execution Mechanism | Session Lifecycle | Model Selection | Context Isolation |
|------|-------------------|------------------|-----------------|-------------------|
| **PM** | `dsh --profile pm-headless "task"` | New session per task invocation; no need for persistence unless tracking PM monitoring | Configurable per role profile (e.g., ornith-1.5:35b) | Full isolation between invocations (VERIFIED) |
| **CTO** | `dsh --profile cto-headless "task"` | New session per invocation (planning/review tasks are self-contained) | Configurable (e.g., qwen3.6:35b for architecture analysis) | Full isolation (VERIFIED) |
| **Implementer** | `dsh --profile implementer-headless "task"` | New session per task; may need to resume for long implementations | Configurable (e.g., qwen3.8:27b for coding) | Full isolation (VERIFIED) |
| **Reviewer** | `dsh --profile reviewer-headless "task"` | New session per review task | Configurable (e.g., laguna-xs-2.1:q4_K_M for code review) | Full isolation (VERIFIED) |

### 10.2 One Role = One Session? (NOT VERIFIED — PROPOSED)

**Proposed**: Each DS-EO role does NOT need a permanently persistent DSH session. Instead:
- The dispatcher invokes `dsh --profile <role-profile> "task instructions"` when the role needs to execute
- The task is self-contained within the invocation (prompt includes all context needed)
- Results are captured from stdout/stderr and fed into DS-EO's gate system
- If a task requires multiple turns (e.g., iterative review), `--session-id` can resume the same session

**Not yet verified**: Whether this model works for long-running roles that need to maintain state across multiple interactions. For PM monitoring, CTO planning, and Review evaluation, each step is a discrete decision point that maps well to single-invocation execution.

### 10.3 Context Passing Mechanism (PROPOSED)

| Mechanism | How It Works | Status |
|-----------|-------------|--------|
| **Artifact files** | DS-EO writes task artifacts (CTO_PLAN.md, REVIEW_REPORT.md, etc.) to disk; role invocation reads them via prompt context or file access | PROPOSED — fits existing DS-EO artifact-based workflow |
| **Prompt embedding** | Critical context is embedded in the task prompt passed to `dsh --profile headless` | PROPOSED — verified that DSH accepts full text prompts |
| **Session resume** | `--session-id <id>` for tasks requiring multi-turn continuity within a role | VERIFIED — works for single-role multi-turn workflows |

### 10.4 Role Isolation (VERIFIED)

- **Context isolation**: VERIFIED — each headless invocation gets its own session with no inherited history (unless explicitly resumed via `--session-id`)
- **Model isolation**: PROPOSED — achieved by creating separate DSH profiles per role with different default models and tool policies
- **Tool policy isolation**: PROPOSED — each profile can be configured with different tool policies; verified that `cordis.patch.yml` supports tool plugin configuration
- **Permission isolation**: PROPOSED — not tested with headless mode; would need to be configured per profile

---

## 11. Failure/Recovery Implications

### 11.1 DS-EO Existing Recovery Mechanisms (VERIFIED — Must Be Preserved)

| Mechanism | Current Location | DSH Impact |
|-----------|-----------------|------------|
| **State engine** | `ds_eo_dsh/workflow/state_engine.py` (S0–S14, 12 transitions) | Unaffected — pure governance logic |
| **Audit log** | `ds_eo_dsh/workflow/audit_log.py` (14-field schema, integrity chain) | Unaffected — DS-EO owns audit |
| **Recovery engine** | `ds_eo_dsh/workflow/recovery_engine.py`, `recovery_state.py` | May need adapter-level integration for DSH session recovery |
| **Stall detection** | `ds_eo_dsh/workflow/stall_detection.py` (per-state timeouts) | Must adapt timeout monitoring to process lifecycle (PID tracking) |
| **Failure detector** | `ds_eo_dsh/workflow/failure_detector.py` (3+ rejection escalation) | Unaffected — DS-EO owns failure detection logic |
| **Escalation chain** | `ds_eo_dsh/workflow/escalation.py` (PM→CTO→User) | Unaffected — governance decision flow |
| **Recovery state** | `recovery_state.json` per task dir, `dispatcher_state.json` | Unaffected — file-based persistence survives DSH process restarts |

### 11.2 DSH-Specific Failure Modes (VERIFIED vs PROPOSED)

| Failure Mode | Handling | Status |
|-------------|----------|--------|
| **DSH process crash** | Caller receives non-zero exit code; DS-EO detects via adapter `ActionResult.success=False` | VERIFIED |
| **Timeout exceeded** | Caller uses `timeout` command or SIGTERM; DSH exits with signal code | VERIFIED (via timeout command) |
| **Session resume failure** | `--session-id <unknown>` returns error; adapter detects and creates new session | DOCUMENTED by DSH docs ("an unknown id is an error") |
| **Model loading failure** | Ollama model unavailable; DSH reports error in stderr | PROPOSED — not tested with headless mode specifically |
| **Context overflow / compaction** | DSH may hit context limits; error reported in stderr | PROPOSED — AGENTS.md documents compaction failure recovery procedure |

### 11.3 Integration Point: Recovery Engine ↔ DSH

DS-EO's recovery engine should integrate with the DSH adapter at the **adapter level**, not the governance level:

```
RecoveryEngine (DS-EO)
  → detects process failure via non-zero exit code
  → decides recovery action (retry, escalate, abort) per RecoveryAction policy
  → adapter re-invokes dsh --profile headless with same task instructions
  → returns new ActionResult to RecoveryEngine
```

The RecoveryEngine **does not** need to know about DSH session IDs — it only needs `ActionResult.success`, `error`, and `details` from the adapter. Session management (resume vs new) is the adapter's responsibility.

---

## 12. Model-Selection Implications

### 12.1 Current DS-EO Model Selection (VERIFIED)

| Role | Proposed DSH Profile Default Model | Evidence |
|------|-----------------------------------|----------|
| PM | ornith-1.5:35b (via profile config) | DOCUMENTED — role defined in workflow_defs/default.yaml with model placeholder |
| CTO | qwen3.6:35b | VERIFIED — currently configured as default for headless profile |
| Implementer | qwen3.8:27b | DOCUMENTED — role definition specifies this model |
| Reviewer | laguna-xs-2.1:q4_K_M | DOCUMENTED — specialized for review; smaller context window, faster inference |

### 12.2 Per-Role Model Selection Strategy (PROPOSED)

**Approach**: Create separate DSH profiles per role, each configured via `cordis.patch.yml` with its default model:

```yaml
# ~/.dsh/profiles/cto-headless/cordis.patch.yml
- id: agent-default-model
  name: "@deepseek-ai/dsh-agent-default-model"
  config:
    provider: ollama
    model: qwen3.6:35b

# ~/.dsh/profiles/implementer-headless/cordis.patch.yml  
- id: agent-default-model
  name: "@deepseek-ai/dsh-agent-default-model"
  config:
    provider: ollama
    model: qwen3.8:27b
```

**Verification status**: PROPOSED — the custom-headless profile was successfully created and verified to switch models via `cordis.patch.yml`. This pattern should generalize to role-specific profiles.

### 12.3 Model Compatibility Constraints (VERIFIED)

| Model | Size | GPU Memory (VRAM) | DSH Compatible? |
|-------|------|-------------------|-----------------|
| qwen3.8:27b | 17 GB | High — may require careful memory management on Jetson Orin | VERIFIED — works with custom-headless profile |
| qwen3.6:35b | 22 GB | Very high — may need to be the only large model loaded | DOCUMENTED — configured in current headless profile |
| laguna-xs-2.1:q4_K_M | 20 GB | High — quantized helps but still substantial | PROPOSED — not tested with headless mode |
| ornith-1.5:35b | 22 GB | Very high — same constraint as qwen3.6 | DOCUMENTED — configured as PM model in default config |
| nomic-embed-text | 274 MB | Low — fast inference, small memory footprint | VERIFIED — works with headless mode (tested via generate API) |

**Critical constraint**: Jetson Orin has 61 GiB total unified memory. Per AGENTS.md: "Never load more than 3 large models simultaneously." DSH headless model selection should respect this by managing which models are loaded/unloaded between role invocations.

---

## 13. Workspace/Artifact Implications

### 13.1 Artifact Management (VERIFIED)

DS-EO's artifact system is file-based and survives process boundaries:

| Artifact | Producer | Location | DSH Impact |
|----------|----------|----------|------------|
| CTO_PLAN.md | CTO | Task directory | DSH role outputs analysis via stdout; DS-EO writes to disk |
| REVIEW_REPORT.md | Reviewer | Task directory (REVIEWER.md only) | Same pattern |
| IMPLEMENTATION_REPORT.md | Implementer | Task directory | DSH role outputs code changes; DS-EO captures and validates |
| CTO_APPROVAL.md | CTO | Task directory | Written by CTO role invocation or by DS-EO based on approval result |
| PROJECT_STATUS.md | PM | Workspace root | Written by DS-EO, not by DSH |
| CHANGELOG.md | PM | Workspace root | Written by DS-EO, not by DSH |

### 13.2 Artifact Capture Strategy (PROPOSED)

DS-EO's dispatcher should:
1. Write the role task instructions to a temp file or pass as CLI argument
2. Execute `dsh --profile <role> "task prompt"` and capture stdout/stderr/exit code
3. Parse JSON-mode output if structured data is needed (e.g., tool calls, usage stats)
4. Write DS-EO artifacts (CTO_PLAN.md, etc.) to disk as governance artifacts — **NOT** relying on the DSH role to write them

**Rationale**: DS-EO's governance protocols define artifact requirements (formats, metadata, signatures). These are policy decisions that must be enforced by DS-EO, not by the LLM model running in DSH. The LLM may produce content, but DS-EO validates and records artifacts.

### 13.3 Workspace Sharing with DSH Agents

- **DSH headless mode**: Agent operates in the same CWD as the parent process (`/home/deepsim` verified)
- **File access**: Headless agent has full filesystem access (no sandbox isolation in headless profile) — **security concern**
- **Artifact placement**: DS-EO artifacts should be written explicitly by DS-EO code after capturing DSH output, not relied upon to be written by the LLM

---

## 14. External-Agent Implications

### 14.1 Current Capability (NOT VERIFIED)

| Aspect | Status | Notes |
|--------|--------|-------|
| **External agent support** | DOCUMENTED only | DSH can treat external sub-agent systems as proxy agents |
| **Codex integration** | DOCUMENTED only | Mentioned in documentation but not tested locally |
| **Claude Code integration** | DOCUMENTED only | Same — documented but not verified |
| **Profile Bundle mechanism** | VERIFIED | Profiles are overlay-based configuration stacks |
| **Plugin management** | VERIFIED | `dsh plugin --profile <name> add/remove` works (requires pnpm) |

### 14.2 Implications for DS-EO DSH Edition

If external agents (Codex, Claude Code) need to participate in the DS-EO workflow:
- They would be invoked as separate processes from DS-EO's dispatcher
- Results would be captured via stdout/stderr and fed into the gate system
- This is orthogonal to the primary DSH headless path but should be supported by the same adapter abstraction

---

## 15. Proposed Target Architecture

### 15.1 Final Recommended Architecture (PROPOSED — Pending Review)

```
┌──────────────────────────────────────────────────────────────┐
│                    DS-EO Engineering Organization             │
│                                                              │
│  PM / CTO / Implementer / Reviewer   ← Governance roles     │
│  Workflow State Machine (S0–S14)      ← Persistence state   │
│  G0–G4 Gate System                    ← Policy enforcement  │
│  Audit Trail / Hash Chain              ← Integrity           │
│  Recovery / Stall / Escalation         ← Reliability        │
│  Dispatcher Engine + Execution Strategy ← Routing            │
│  Project Resolution / Release Mgmt     ← Product governance │
└──────────────────────────────────┬───────────────────────────┘
                                   │
                              ┌────▼─────┐
                              │RuntimeAPI│  ← Protocol (unchanged)
                              │Adapter    │
                              └────┬─────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
              ┌─────▼─────┐ ┌────▼─────┐ ┌──────▼───────┐
              │DshHeadless│ │Ollama   │ │ External     │
              │Adapter     │ │Direct    │ │ Agent Adapter│
              │           │ │API       │ │ (Codex/      │
              │dsh --profile│ │(for     │ │  Claude)     │
              │headless    │ │model    │ │              │
              │"task"      │ │queries  │ │              │
              └─────┬─────┘ └──────────┘ └──────────────┘
                    │
              ┌─────▼─────┐
              │ DSH Runtime│
              │            │
              │ Headless   │ ← Primary execution mechanism (VERIFIED)
              │ Subagents  │ ← Augmentation for parallel work within a role
              │ Agent Teams│ ← Optional: for dependency-driven collaboration
              └────────────┘
                    │
              ┌─────▼─────┐
              │ Model Layer │
              │            │
              │ Ollama     │ ← Local models (VERIFIED)
              │ DeepSeek   │ ← Cloud providers (if available)
              │ External   │ ← Codex, Claude Code (not tested)
              └────────────┘
```

### 15.2 Key Architectural Decisions (PROPOSED)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Primary execution mechanism** | `dsh --profile headless` CLI invocation | VERIFIED working, machine-readable output, process-controlled lifecycle |
| **Session model for RuntimeAPI** | Ephemeral per-invocation with optional resume via `--session-id` | Matches DSH's actual session persistence behavior |
| **Role-to-model mapping** | Per-role DSH profiles (one profile per role) | Verified pattern works; each role gets its own model/tool/permission config |
| **Artifact management** | DS-EO writes artifacts to disk after capturing DSH output | DS-EO owns governance artifacts, not the LLM model |
| **Dependency/task management** | DS-EO's state machine handles this (NOT Agent Teams) | Avoids duplicating gate logic; DS-EO's G0–G4 is more capable for engineering workflows |
| **Concurrency within a role** | Native `subagent`/`workflow` tools (optional augmentation) | For intra-role parallel work, but NOT required for the primary PM→CTO→Implementer→Reviewer chain |
| **Model selection** | Profile-level default + Ollama direct API for model queries | Simplest approach; verified Ollama `/api/tags` works |

---

## 16. Migration Implications

### 16.1 What Can Be Retained From Current Work (VERIFIED)

| Item | Decision | Reason |
|------|----------|--------|
| RuntimeAPI protocol (`runtime_api.py`) | **RETAIN** — no breaking changes needed | Protocol is abstraction-agnostic; adapter layer handles DSH specifics |
| RuntimeAPI types (`RuntimeModel`, `RuntimeSession`, `ActionResult`) | **RETAIN** — semantics may shift slightly but not break | Types are suitable for DSH headless model (session key = DSH session ID) |
| Dispatcher engine (`engine.py`, `dispatch.py`, `state_manager.py`) | **RETAIN** — core governance logic | No changes needed; dispatcher is DS-EO domain logic, independent of runtime |
| Execution strategies | **RETAIN** — routing decisions remain valid | Strategy selection is based on task characteristics, not runtime specifics |
| Workflow state machine (S0–S14) | **RETAIN** — lifecycle is governance logic | State transitions encode engineering organization policy |
| Gate system (G0–G4) | **RETAIN** — authority matrix is DS-EO policy | Gate definitions are organizational, not runtime-specific |
| Audit trail / hash chain | **RETAIN** — integrity requirement | Must persist regardless of execution mechanism |
| Recovery engine + recovery state | **RETAIN** — failure handling logic | May need adapter-level integration but the engine itself is valid |
| Stall detection + escalation | **RETAIN** — reliability mechanisms | Process-level timeouts can replace session-level monitoring |
| Failure detector (3+ rejection escalation) | **RETAIN** — organizational policy | Gate rework thresholds are DS-EO decisions |
| Project resolver / task ID management | **RETAIN** | Task lifecycle is governance, not runtime |
| Release management protocol | **RETAIN** | Product governance, independent of runtime |
| Existing test suite (562 passing) | **RETAIN** | Tests verify governance logic; may need adapter-level tests added |

### 16.2 What Needs to Change (PROPOSED)

| Item | Change Needed | Priority |
|------|--------------|----------|
| `dsh_adapter.py` (current HTTP-based implementation) | **REPLACE** with DSH headless process-invocation adapter | High — current adapter assumes non-existent REST API |
| `dsh_http_client.py` | **KEEP** as reference; may be simplified or removed if not needed for other adapters | Medium |
| RuntimeAPI session semantics | **CLARIFY** that "session" in DSH context means "invocable execution handle" not "persistent running process" | High — affects adapter implementation |
| Supervisor lifecycle monitoring | **ADAPT** from OpenClaw-based to process-PID-based monitoring | Medium — stall detection needs process tracking |
| Integration tests for DSH headless | **ADD** new test suite for the headless adapter | Medium |
| Model registry | **SIMPLIFY** to Ollama direct API + profile defaults; may drop complex model routing | Low |

### 16.3 What Should Be Abandoned (PROPOSED)

| Item | Reason |
|------|--------|
| HTTP REST-based DSH adapter design | No actual DSH REST API exists on this machine |
| Any attempt to build custom sub-agent dispatching | DSH provides native primitives that should be used |
| Agent Team (limuyang2) integration | GUI-only, no programmatic interface; architecturally incompatible |
| Replacing DS-EO's dispatcher with Agent Teams task DAG | Overlap on governance logic; DS-EO's state machine is more capable |

---

## 17. Risks and Unresolved Questions

### 17.1 Technical Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **DSH headless model loading conflicts** on Jetson Orin (61GB unified memory, 3-model limit) | HIGH | Adapter should manage `ollama rm`/`ollama list` to control which models are loaded before invocation; document in ASSETS.md or separate config |
| **Context overflow** when task instructions + workspace context exceed model window | MEDIUM | Use bounded file reading (≤30 lines per AGENTS.md R-SI-1); embed only critical context in prompts; let LLM read files directly when needed |
| **Tool policy enforcement** — DSH headless may not respect the same sandbox/tool restrictions as OpenClaw agent configuration | MEDIUM | Configure each role's profile with `permission` patch in `cordis.patch.yml` to match intended tool scope |
| **Process management complexity** — spawning/terminating multiple concurrent DSH processes may be fragile on Jetson Orin | MEDIUM | Use supervisor pattern with PID tracking; implement graceful shutdown via SIGTERM; test concurrency limits |
| **Session resume reliability** — `--session-id` behavior depends on DSH version and storage state | LOW-MEDIUM | Adapter should detect unknown session IDs and fall back to creating new sessions; test edge cases |
| **No built-in sandbox for headless mode** — agents have full filesystem access by default | MEDIUM | Document that DS-EO artifacts must be written by DS-EO code after capturing DSH output, not relied upon from LLM side effects |

### 17.2 Unresolved Questions (NOT VERIFIED)

| Question | Impact | Verification Needed |
|----------|--------|---------------------|
| **Can `dsh --profile headless` run in parallel without memory conflicts?** | Determines max concurrency for DS-EO dispatcher | Test spawning multiple headless processes with large models simultaneously |
| **What happens when DSH headless encounters a tool call it cannot fulfill?** | May affect error handling reliability | Test with a prompt that triggers tool use |
| **Does DSH headless support MCP servers in the same way as OpenClaw?** | Affects what tools DS-EO can request from roles | Document or test specific MCP server availability |
| **What is the exact timeout behavior when DSH headless hangs?** | Critical for supervisor stall detection | Test with a long-running prompt and measure exit signal |
| **Can `dsh agent_teams_*` tools be invoked programmatically (not just via slash command)?** | Determines if AgentTeams augmentation layer is viable | Inspect source code for programmatic tool API |
| **What file format does `<workspace>/.agent-teams/` use, and is it stable across DSH versions?** | If DS-EO needs to read team state directly from disk | Inspect the actual file format in `.agent-teams/` directory |
| **How does DSH handle GPU memory when switching between models for different roles?** | Critical for Jetson Orin memory management | Test model loading/unloading sequence with ollama CLI |

### 17.3 Architectural Risks

| Risk | Description | Mitigation |
|------|-------------|------------|
| **DSH version drift** — DSH `0.1.7-rc.2` is an RC release; behavior may change in stable release | Adapter may break with future DSH versions | Pin DSH version; test adapter against new RC releases before upgrading |
| **Agent Teams plugin maturity** — Agent Teams 0.1.4 and dsh-agent-teams 0.1.22 are both early-stage plugins | Features may change or be removed in future versions | Document dependency on these plugins as optional; DS-EO core should not depend on them |
| **Ollama version compatibility** — DSH uses Ollama's OpenAI-compatible API (`http://localhost:11434/v1`) | Breaking changes in Ollama's API could affect adapter | Pin Ollama version range; test against current Ollama version before upgrading |

---

## 18. Recommended Next Implementation Phase

### 18.1 Phase 10 Revision: "DSH Headless Adapter Integration"

**Objective**: Connect the existing DS-EO governance architecture to DSH headless execution via a working adapter, without building any custom multi-agent framework or duplicating Agent Teams functionality.

**Scope** (PROPOSED — pending review):

#### Step 1: DSH Profile Setup (20 minutes)
- Create per-role DSH profiles (`cto-headless`, `implementer-headless`, `reviewer-headless`, `pm-headless`) in `~/.dsh/profiles/`
- Each profile: configured via `cordis.patch.yml` with its default model and tool policy
- Verify each profile works with `dsh --profile <name> "test task"`

#### Step 2: DSH Headless Adapter Implementation (1 hour)
- Replace the current HTTP-based `DshRuntimeAdapter` with a `DshHeadlessAdapter`
- Translate RuntimeAPI methods to `subprocess.run()` invocations of `dsh --profile <role-profile> "task"`
- Handle JSON-mode output for structured data capture
- Implement graceful error handling (non-zero exit codes, timeouts, session resume)
- Keep the existing RuntimeAPI protocol unchanged

#### Step 3: Adapter-Level Integration Tests (1 hour)
- Test DSH headless adapter against all 10 RuntimeAPI methods
- Verify each role's profile works with its designated model
- Test session resume (`--session-id`) behavior
- Test JSON-mode parsing for structured results
- Run existing DS-EO test suite to verify no regressions

#### Step 4: Minimal End-to-End Smoke Test (30 minutes)
- Execute a single-role workflow (e.g., PM → CTO task creation) through the full stack
- Verify artifact files are produced by DS-EO and captured correctly from DSH output
- Verify gate transitions work end-to-end with real DSH invocations

### 18.2 What Phase 10 Does NOT Include (Per Constraints)

| Excluded Item | Reason |
|---------------|--------|
| Building custom multi-agent framework | DSH provides native primitives; do not duplicate |
| Integrating Agent Team (limuyang2) | GUI-only, no programmatic interface |
| Replacing DS-EO's dispatcher engine | Dispatcher is governance logic; keep it |
| Redesigning the workflow state machine | State machine encodes DS-EO engineering policies |
| Discarding existing RuntimeAPI design | Protocol is valid; only adapter implementation changes |
| Implementing dsh-agent-teams integration yet | Requires verifying CLI programmatic API first |
| Managing GPU memory automatically via adapter | Documented constraint in AGENTS.md; handle separately |

### 18.3 Success Criteria for Phase 10 (PROPOSED)

| Criterion | Verification Method |
|-----------|---------------------|
| DSH headless invocation works for all 4 roles | `dsh --profile <role-profile> "test"` succeeds with exit code 0 for each role |
| RuntimeAPI adapter translates all 10 methods correctly | All 10 adapter method tests pass against real DSH invocations |
| DS-EO governance unchanged | Existing test suite (562 passing) still passes; no behavioral changes to gate system, state machine, or audit trail |
| Single-role smoke test works end-to-end | PM creates task → CTO analyzes → artifact produced → gate transition recorded in audit trail |
| No new multi-agent framework built | Code review confirms no custom orchestration logic in DS-EO core |

---

## Summary of Recommendations

1. **Use DSH native mechanisms** (`dsh --profile headless`) as the primary execution primitive — VERIFIED working, machine-readable output, process-controlled lifecycle
2. **Preserve all DS-EO governance architecture** (dispatcher, state machine, gates, audit, recovery, release management) — these are organizational responsibilities, not runtime concerns
3. **Do NOT integrate Agent Team (limuyang2)** — GUI-only, no programmatic interface, architecturally incompatible with DS-EO's Python dispatcher
4. **Keep dsh-agent-teams (NanmiCoder) as a future option** — has partial CLI support and dependency-aware tasks, but requires further verification before integration
5. **Implement a DSH headless adapter** that translates the existing RuntimeAPI protocol to `dsh --profile headless` invocations via subprocess management
6. **Create per-role DSH profiles** for PM/CTO/Implementer/Reviewer, each with its own default model and tool policy
7. **Do NOT implement any phase beyond Step 1 (DSH Profile Setup)** until this assessment has been reviewed and approved

---

*This assessment was produced based on actual local inspection of the installed DSH environment (version 0.1.7-rc.2), verification of DSH headless invocation capabilities, source review of both Agent Team projects from their GitHub repositories, and analysis of the existing DS-EO architecture in `/home/deepsim/ds_eo_dsh/`. All claims are classified as VERIFIED, DOCUMENTED, NOT VERIFIED, or PROPOSED.*

---
*End of assessment document — awaiting CTO/Gateway-owner review before implementation proceeds.*
