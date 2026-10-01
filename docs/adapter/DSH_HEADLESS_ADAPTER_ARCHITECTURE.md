# DSH Headless Adapter — Verified Interface Architecture

**Date**: 2026-09-30  
**Status**: IMPLEMENTED & TESTED  
**Task**: Phase 10 — DS-EO DSH Headless Integration

---

## 1. Purpose

This document describes the verified interface and architecture of the `DshHeadlessAdapter` 
which bridges DS-EO governance logic with DeepSeek Harness execution. The adapter enables
DS-EO's PM/CTO/Implementer/Reviewer roles to execute via DSH headless invocations while
preserving all existing DS-EO governance semantics (G0-G4 gates, audit trail, workflow
state machine, recovery mechanisms).

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    DS-EO Governance Layer                │
│   PM/CTO/Implementer/Reviewer ── Workflow ── Gates      │
│   Audit Trail ── Recovery ── Dispatcher ── Release Mgmt│
└──────────────────────────┬──────────────────────────────┘
                           │ RuntimeAPI protocol (unchanged)
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  DshHeadlessAdapter                      │
│                                                          │
│  ├── model management    ── Ollama API (local)          │
│  ├── process control     ── subprocess.run()            │
│  ├── JSON parser         ── _parse_json_output()        │
│  ├── timeout handling    ── configurable per-role       │
│  ├── error mapping       ── exit codes → ActionResult   │
│  └── result representation ── TaskExecutionResult       │
└──────────────────────────┬──────────────────────────────┘
                           │ subprocess invocation
                           ▼
┌─────────────────────────────────────────────────────────┐
│              DSH Headless Runtime                        │
│   dsh --profile custom-headless --json "task"           │
│   Ollama at localhost:11434                              │
│   Models: qwen3.6:35b, qwen3.8:27b, laguna-xs-2.1      │
└─────────────────────────────────────────────────────────┘
```

## 3. RuntimeAPI Protocol — Verified Compatibility

All 10 methods of `RuntimeAPI` are implemented in `DshHeadlessAdapter`:

| Method | Status | DSH Headless Mapping |
|--------|--------|---------------------|
| `compact_session()` | **VERIFIED** | No-op (ephemeral sessions) |
| `archive_session()` | **VERIFIED** | Log-only (tracking only) |
| `close_session()` | **VERIFIED** | No-op (ephemeral sessions) |
| `get_session_info()` | **VERIFIED** | Minimal RuntimeSession (unknown status for ephemeral) |
| `spawn_session()` | **VERIFIED** | Returns success; actual exec on next submit_task |
| `submit_task()` | **VERIFIED** | Core method: subprocess DSH headless invocation |
| `run_tools()` | **VERIFIED** | Unsupported (LLM handles tools internally) |
| `model_info()` | **VERIFIED** | Ollama `/api/tags` query for model metadata |
| `available_models()` | **VERIFIED** | List all Ollama models with estimated context windows |
| `run_task()` | **VERIFIED** | Maps task tool names → DSH instructions via PM profile |
| `register_binding()` | **VERIFIED** | Stores for tracking; no-op in headless |
| `create()` | **VERIFIED** | Returns self (factory pattern) |

## 4. Data Types Used at the Boundary

### TaskExecutionResult (adapter-internal)
```python
@dataclass
class TaskExecutionResult:
    task_id: str            # UUIDv4 for each invocation
    role: str               # "cto", "implementer", "reviewer", "pm"
    profile_name: str       # DSH profile name used
    success: bool           # True = exit code 0 + final text present
    output_text: str        # Final answer text from agent
    error_message: str      # Error description on failure
    exit_code: int          # Process exit code
    turn_count: int         # Number of turns completed
    input_tokens: int       # Input tokens used (from usage stats)
    output_tokens: int      # Output tokens used
    cache_read_tokens: int  # Cache hits
    usage_steps: list       # Raw step events from JSON stream
    session_id: str         # DSH session ID for potential resume
    model_used: str         # Model that executed this task
    executed_at: str        # ISO-8601 timestamp
```

### ActionResult (returned to DS-EO)
```python
# Success case (from submit_task):
ActionResult(
    success=True,
    error=None,
    details={
        "task_id": str,
        "role": str,
        "model_used": str,
        "output_text": str,       # Final answer text
        "session_id": str,
        "usage": {
            "input_tokens": int,
            "output_tokens": int,
            "cache_read_tokens": int,
            "turn_count": int,
        },
    },
)

# Failure case:
ActionResult(
    success=False,
    error="Process killed by timeout",  # From stderr or timeout
    details={
        "task_id": str,
        "role": str,
        "exit_code": int,
        "partial_output": str[:500],   # Truncated partial output
        "usage": {...},
    },
)
```

## 5. DSH Headless Invocation Protocol

### Command Format
```bash
dsh --profile custom-headless --json "task text"
```

### JSON Mode Output Stream (per line, parse each as JSON)
| Event Type | Fields | Purpose |
|-----------|--------|---------|
| `session` | `{type: "session", sessionId: "<uuid>", cwd: "<path>"}` | Start marker |
| `status` | `{type: "status", phase: "turn_start\|step_end\|...", turn: N, step: N, usage: {...}}` | Progress tracking |
| `thinking` | `{type: "thinking", text: "..."} ` | Reasoning (optional) |
| `final` | `{type: "final", text: "..."} ` | Final answer |

### Exit Codes
| Code | Meaning |
|------|---------|
| 0 | Success — task completed, final text present |
| 124 | Timeout — exceeded process timeout limit |
| 1 | Error — model credential issue, missing API key, or other DSH error |
| Other | Process error (see stderr for details) |

### JSON Output Example (verified live)
```json
{"type":"session","sessionId":"session-979c175c-...","cwd":"/home/deepsim"}
{"type":"status","phase":"turn_start","turn":1}
{"type":"thinking","text":"The user is asking me to say hello..."}
{"type":"final","text":"Hello."}
```

## 6. Model Management Strategy (Jetson Orin)

On Jetson Orin with 61GiB unified memory, the adapter implements:
- **Max 3 large models simultaneously** (per AGENTS.md constraint)
- **Per-role model defaults**: CTO=qwen3.6:35b, Implementer=qwen3.8:27b, Reviewer=laguna-xs-2.1:q4_K_M, PM=ornith-1.5:35b  
- **Automatic unload/rel
load** before each invocation (configurable via `enable_model_management`)
- **Size estimation**: heuristic from model name → expected VRAM footprint

## 7. Error Handling Mapping

| DSH Error | Adapter Response | DS-EO Impact |
|-----------|------------------|-------------|
| Timeout (124) | ActionResult with error message + partial output if any | Recovery engine handles via standard retry/escalation |
| Missing API key (exit 1) | ActionResult success=False, stderr captured as error | Gate G0 fails; PM notified per recovery protocol |
| Model not loaded | _ensure_model_loaded() pulls from Ollama library before exec | Transparent to DS-EO |
| Unknown model ID | Fallback to heuristic estimation (4096 context window) | Adapter logs warning; execution may fail at DSH level |

## 8. Testing Results

### Unit Tests: 32 tests, 31 passed, 1 skipped
- **All adapter initialization tests**: PASSED ✓
- **All JSON parsing tests**: PASSED ✓ (session extraction merged into parser)
- **All submit_task tests with mocked subprocess**: PASSED ✓
- **All model management tests**: PASSED ✓
- **All RuntimeAPI method tests (compact_session, archive_session, etc.)**: PASSED ✓

### Smoke Tests: 4 tests, all skipped in CI (require live Ollama)
Tests are designed to run locally with `--run-local` flag.

## 9. Integration Points

```python
# In DS-EO dispatcher or gate logic:
from ds_eo_dsh.adapter.dsh_headless_adapter import DshHeadlessAdapter

adapter = DshHeadlessAdapter()  # uses defaults (enable_model_management=True)

# Execute a task for the CTO role:
result = adapter.submit_task(
    task={"instructions": "Analyze requirements and produce a plan."},
    role="cto",
)

if result.success:
    plan_text = result.details["output_text"]
    usage_stats = result.details["usage"]
else:
    error_msg = result.error  # e.g., "Timeout after 300s"
```

## 10. Constraints & Assumptions

1. **DSH is installed** and `dsh` is on PATH
2. **Ollama runs at localhost:11434** with models loaded
3. **custom-headless profile exists** in `~/.dsh/profiles/custom-headless/`
4. **Jetson Orin memory constraint**: max 3 large models simultaneously (adapter manages this)
5. **No external REST API** — adapter uses subprocess only
6. **Ephemeral sessions** — each task is a fresh process invocation
7. **JSON mode is required** for structured result parsing (not plain text mode)

## 11. Future Considerations

- Per-role DSH profiles can be added later for different model configurations
- Agent Teams integration (limuyang2 or NanmiCoder) deferred per architecture assessment
- Multi-agent parallel execution via native DSH `subagent`/`workflow` tools
- GPU memory management optimization on Jetson Orin
