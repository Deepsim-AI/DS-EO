---
produced_by: ollama/qwen3.6:35b
session_id: b98d4488-5428-4eba-99c8-ecce7da4f2a2
produced_at: 2026-08-08T23:14:00-07:00
role: CTO
task_id: TASK_DS_EO_035
gate: G1
---

# CTO Plan — TASK_DS_EO_035: Phase 7 - Session Health Real OpenClaw API Integration

## Problem Statement

TASK_DS_EO_001 built the session health system skeleton (discovery, classification, policy, executor, monitor) but left all **destructive actions** as stubs because the real OpenClaw API was unavailable at the time. The known limitation stated: "_COMPACT integration requires real OpenClaw API (post-deployment)._".

Now that `openclaw sessions compact` is confirmed available via CLI/RPC, we implement the real integrations for all lifecycle actions.

## Scope - Five Actions Need Real Integration

### Action 1: COMPACT (_perform_compaction)
**Current**: Returns None (stub).  
**Required**: Call `openclaw sessions compact <session_key> --json` via subprocess. Parse JSON response to confirm compaction succeeded and return post-compact context size.

### Action 2: ARCHIVE
**Current**: Returns mock {"archived": true}.  
**Required**: Use `openclaw sessions export-trajectory <key>` to export session data, store locally in archive directory (configurable path), then optionally run `openclaw sessions cleanup` or manually remove the exported session.

### Action 3: CLOSE
**Current**: Returns mock {"closed": true}.  
**Required**: No direct "close" API exists in OpenClaw CLI. Close should mark the session inactive via gateway session state update, or use the cleanup mechanism to clean up the session from the store.

### Action 4: MONITOR (enhanced monitoring)
**Current**: Mock {"monitoring_enabled": true}.  
**Required**: Register with LivenessChecker enhanced polling mode - increase check frequency, add anomaly detection hooks.

### Action 5: WARN (notification delivery)
**Current**: Mock {"warning_recorded": true}.  
**Required**: Emit via the notification system (email/webhook/push to PM agent session).

## Implementation Plan

### Step 1: Create ds_eo_openclaw/session_health/openclaw_api.py [NEW]

A single module providing thin wrappers around OpenClaw CLI commands:

```python
class OpenClawAPI:
    """Thin wrapper for OpenClaw CLI session lifecycle operations."""
    
    def compact_session(self, session_key: str, agent_id: Optional[str] = None) -> dict
        # Calls: openclaw sessions compact <key> --json [--agent <id>]
        # Returns parsed JSON result with success/failure + context info
    
    def archive_session(self, session_key: str, agent_id: Optional[str] = None, dest_dir: Optional[str] = None) -> dict
        # Calls: openclaw sessions export-trajectory <key> --json
        # Saves output to configured archive directory
    
    def close_session(self, session_key: str, agent_id: Optional[str] = None) -> dict
        # Uses sessions cleanup or marks inactive via gateway RPC
        # No direct "close" API - design decision needed
    
    def get_session_info(self, session_key: str, agent_id: Optional[str] = None) -> dict
        # Calls: openclaw sessions list --json and filters to find target
        # Returns context size, turn count, status, etc.
    
    def warn_session(self, session_key: str, message: str) -> dict
        # Emits notification - could be via gateway RPC or file-based
```

**Design Decision**: Use `subprocess.run()` with timeout for all CLI calls (no Python library dependency). All calls go through the running OpenClaw gateway via WebSocket (CLI handles auth). Add 60s default timeout per call. Handle non-zero exit codes as errors.

### Step 2: Update executor.py to use real API

Replace all stub methods in SessionHealthExecutor:
- `_perform_compaction()` -> OpenClawAPI.compact_session() + parse result for context reduction verification
- `_execute_archive()` -> OpenClawAPI.archive_session() + verify file exists post-archive
- `_execute_close()` -> OpenClawAPI.close_session() or gateway RPC call
- `_execute_monitor()` -> Configure LivenessChecker polling interval via config
- `_execute_warn()` -> Emit to PM agent session via sessions_send

### Step 3: Update discoverer.py to get real context sizes

Current discoverer estimates context size. Add a method that queries the actual OpenClaw session store for precise byte/token counts.

### Step 4: Update tests

- Add integration tests for all new API methods (mocked at subprocess level - no live gateway needed)
- Add end-to-end test exercising COMPACT -> verify reduction -> verify post_metrics

### Step 5: Update documentation

- agents/pm.md - Document real-world session health capabilities
- ds_eo_manifest.yaml - Already has entry, just needs phase update comment

## Acceptance Criteria

1. **COMPACT**: Calls real openclaw sessions compact CLI; returns accurate post-compact context size; verification works (pre > post confirms success)
2. **ARCHIVE**: Exports session via export-trajectory; file exists in archive directory on disk; returns verified result
3. **CLOSE**: Marks or removes session from store safely; tested with non-active sessions only
4. **MONITOR**: Actually changes polling behavior (verified by inspecting internal state)
5. **WARN**: Notification is delivered to PM agent session (tested via mock)
6. **All 38 existing tests pass** + new integration tests for all 5 actions
7. **Zero breaking changes** to existing API surface

## Risk Assessment

- **Low risk**: All changes are additive/substitution - replaces stubs with real implementations. No refactoring of existing modules.
- **Dependency**: Requires OpenClaw gateway to be running (already true in production).
- **Security**: CLI calls use same auth as the gateway configuration (no new credentials needed).

## Architecture Diagram

```
SessionHealthExecutor
    |
    +-- _execute_compact() ----> OpenClawAPI.compact_session() ---> subprocess -> openclaw sessions compact
    |                               |
    |                               +--> parse JSON result -> verify pre > post context size
    |
    +-- _execute_archive() ----> OpenClawAPI.archive_session() ----> subprocess -> openclaw sessions export-trajectory
    |
    +-- _execute_close() ----> OpenClawAPI.close_session() --------> gateway RPC / cleanup
    |
    +-- _execute_monitor() ----> Update LivenessChecker interval ---> internal state change
    |
    +-- _execute_warn() ----> Notify via PM agent session ---------> sessions_send / file-based
```
