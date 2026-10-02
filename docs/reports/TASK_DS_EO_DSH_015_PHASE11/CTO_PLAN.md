# TASK_DS_EO_DSH_015 — Phase 11: Runtime Adapter Invocation Integration

---
produced_by: qwen3.6:35b (CTO)
session_id: dsh-continue-2024
role: CTO
task_id: TASK_DS_EO_DSH_015
gate: G1
---

## 1. Summary

Phase 11 bridges the workflow engine (`engine.execute_transition`) to a concrete
runtime adapter via the **dispatch client** introduced as WI-1. Prior phases built
the adapter infrastructure (Phases 0–7) and a headless stub + baseline repair
(Phase 10). Phase 11 makes the dispatcher *callable* against a runtime rather
than silently updating internal state only.

WI-1 (`dispatch_client.py`) was authored by the previous session commit but not
yet committed (untracked in git status). This task commits it, wires it into the
engine, adds tests, and documents the env resolution table.

## 2. Gate Sequence

| Gate | Transition | Authority | Decision |
|------|-----------|-----------|----------|
| G1 | Planning → Implementation | User approves CTO's plan | Approve / Request revision |
| G2 | Implementation → Review | Implementer self-declares complete + CTO confirms | Complete? |
| G3 | Review → Approval | Reviewer recommends pass/fail | Passes? |
| G4 | Approval → Complete | CTO final decision | Approve / Reject |

## 3. Work Items

### WI-1: Commit dispatch_client.py (already written)

**Status**: Written, untracked (`ds_eo_dsh/dispatcher/dispatch_client.py`).

Action: Add and commit to repo as part of this task. No modifications needed — the
file is 194 lines, complete per scope.

Key properties (from file):
- Imports `RuntimeAdapterFactory` from `ds_eo_dsh.adapter.runtime_api` (production boundary)
- Never imports a concrete adapter directly
- Resolution order: `DSH_ADAPTER` env → `"headless"` default
- Maps `"headless"`, `"dsh"`, `"openclaw"`, `"auto"` into factory vocabulary
- Returns `{"result": json(TransitionResult), "runtime": name}` contract

### WI-2: Wire dispatch_client into engine.execute_transition(target_agent=...)

**Location**: `ds_eo_dsh/dispatcher/engine.py` — function `execute_transition()`.

**Insert point**: After the execution strategy prepare/release hooks block (line
322 ends with `# ===== END TASK_DS_EO_044 Strategy Hooks =====`) and before
"Step 1: Validate transition" (line 324).

**Contract**: Call `dispatch_client.run()` with a built task dict. The call must be
**non-fatal** — if it raises, log a warning but **do not mutate state** (no file
writes). The engine's existing TransitionResult is honoured; the dispatch result's
`success=False` is logged but does not block the gate transition unless `payload_summary`
indicates a failure that must be surfaced.

```python
if target_agent:
    try:
        dispatch_input = {
            "task_id": task_id,
            "target_agent": target_agent,
            "transition_name": transition_name,
            "from_phase": from_phase,
            "to_phase": to_phase,
            "payload": payload_summary,
        }
        _dispatch_result = dispatch_client.run(dispatch_input)
        if isinstance(_dispatch_result, dict):
            _parsed = json.loads(_dispatch_result.get("result", "{}"))
            if not _parsed.get("success", False):
                logger.warning(
                    "Dispatch for %s→%s (%s to %s) reported failure: %s",
                    task_id, from_phase, target_agent, transition_name,
                    _parsed.get("error", "unknown"),
                )
    except Exception as _dx_err:
        logger.warning(
            "Dispatch client call failed for role=%s (non-fatal): %s",
            target_agent, _dx_err,
        )
```

**Do-not**: No new agents, no gate mechanics changes, no filesystem writes beyond the
adapter boundary. The adapter owns artifact production; the engine only records
whether dispatch succeeded or failed.

### WI-3: Config / env resolution table

`dispatch_client.py` documents the `DSH_ADAPTER` env var and its resolution order
inline in `_resolve_runtime()`. Add a one-table reference in `README.md` under
a new "Runtime Adapter" section documenting:

| Env var | Default | Effect |
|---------|---------|--------|
| `DSH_ADAPTER=headless` | `"headless"` | Headless adapter (no live DSH API) |
| `DSH_ADAPTER=dsh` | — | Real DSH HTTP adapter (requires `DSH_API_BASE`) |
| `DSH_ADAPTER=openclaw` | — | OpenClaw runtime adapter |
| `DSH_API_BASE` | unset | If set + DSH_ADAPTER∈{dsh,headless}, uses HTTP adapter; else headless fallback |

### WI-4: Tests (tests/test_adapter/test_dispatch_client.py)

Four tests, all in `tests/test_adapter/` alongside existing Phase 0/6/7/10
adapter tests:

1. `test_headless_default_creation` — Default runtime resolution produces headless
   adapter via RuntimeAdapterFactory; no env required.
2. `test_build_task_input_correct` — `_build_task_input()` produces the expected
   dict for a valid input (task_id, target_agent, transition_name all present).
3. `test_failure_path` — Mock `RuntimeAdapterFactory.create` to raise → verify
   success=False returned without mutating state.
4. `test_execute_transition_forwards_target_agent` — Lifecycle smoke: call
   `engine.execute_transition()` with `target_agent="cto"` and confirm the dispatch
   bridge executes (verified via mock).

## 4. Definition of Done

- `dispatch_client.py` committed to repo under `ds_eo_dsh/dispatcher/`.
- `engine.execute_transition()` wires the dispatch call post-hooks, per WI-2.
- Env resolution table documented in README.md.
- All 4 tests pass (plus existing full suite stays green).
- CTO_PLAN / gates G1..G4 recorded; TASK_COMPLETION_AUDIT.md produced.

## 5. Risks

- **Non-fatal dispatch**: If dispatch fails, the gate still advances per spec — this
  is correct because the engine does not mutate artifacts itself (the adapter owns
  that). The `success=False` is logged; a G4 review will catch actual misses.
- **Test mocking complexity**: `RuntimeAdapterFactory.create()` needs to be mockable
  without requiring a live Ollama/API instance. Use `unittest.mock.patch`.

## 6. Scope Boundaries

- No new agents, agent configs, or gateway bindings.
- No changes to gate mechanics or state engine transition rules.
- No changes to `dsh_headless_adapter.py` core behavior.
- No filesystem writes beyond the adapter boundary (the adapter handles that).

## 7. File Inventory

| File | Action | Description |
|------|--------|-------------|
| `ds_eo_dsh/dispatcher/dispatch_client.py` | Add (untracked → committed) | WI-1, 194 lines |
| `ds_eo_dsh/dispatcher/engine.py` | Edit (~20 lines added) | WI-2, dispatch bridge call |
| `README.md` | Edit (minor section) | WI-3, env resolution table |
| `tests/test_adapter/test_dispatch_client.py` | Add (NEW, ~50 tests) | WI-4 |
