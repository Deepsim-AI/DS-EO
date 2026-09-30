"""
DS-EO Run-State Reconciliation Layer — Usage Examples

Demonstrates the three core modules: reconciler, error_mapper, and recovery_protocol.

Installation: pip install pytest (for tests); no external dependencies for usage.
Usage: python examples/run_reliability/usage.py

See ds_eo_openclaw/run_reliability/ for implementation details.
"""

# ──────────────────────────────────────────────────────────────────────
# 1. Orphaned Run Detection (reconciler)
# ─────────────────────────
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ds_eo_openclaw.run_reliability.reconciler import detect_orphaned_runs, find_active_sessions, classify_run_state

def example_orphaned_detection():
    """Detect orphaned runs by comparing gateway-side run state against agent sessions."""
    
    # The reconciler queries available APIs to find:
    # - Active runs with no corresponding active session (orphaned)
    # - Active sessions with no corresponding run (stale)
    # - Run-state mismatches between gateway and TUI
    
    print("=== Orphaned Run Detection ===")
    
    # In production, this queries actual OpenClaw APIs:
    #   detect_orphaned_runs()
    #   find_active_sessions()
    # For demonstration, we show the data model:
    
    sample_state = {
        "orphaned_runs": [
            {
                "run_id": "BteeOQT8",
                "session_type": "session",
                "detected_at": "2026-08-13T10:00:00Z",
                "cause": "run completed but session still marked 'finishing context'",
            }
        ],
        "stale_sessions": [
            {
                "session_id": "tui-stale-001",
                "run_type": "no_run",
                "detected_at": "2026-08-13T10:01:00Z",
                "cause": "session still active after run abort completed",
            }
        ],
        "mismatches": []
    }
    
    for orphan in sample_state.get("orphaned_runs", []):
        print(f"  ORPHANED RUN: {orphan['run_id']} — {orphan['cause']}")
    
    for stale in sample_state.get("stale_sessions", []):
        print(f"  STALE SESSION: {stale['session_id']} — {stale['cause']}")
    
    if not sample_state["orphaned_runs"] and not sample_state["stale_sessions"]:
        print("  No orphaned runs detected. State is consistent.")
    
    return sample_state


# ──────────────────────────────────────────────────────────────────────
# 2. Structured Error Classification (error_mapper)
# ──────────────────────────────────────────────────────────────────────

from ds_eo_openclaw.run_reliability.error_mapper import classify_error, ERROR_PATTERNS

def example_error_classification():
    """Classify raw error strings into structured DS-EO error categories."""
    
    print("\n=== Error Classification ===")
    
    # Example: convert opaque error string → structured classification
    raw_errors = [
        "run error: unknown",                          → becomes →  {"category": "UNKNOWN_ERROR", "action": "use recovery protocol"}
        "run timeout exceeded",                        → becomes →  {"category": "TIMEOUT", "action": "check gateway-side run state, retry with timeout"}
        "session disconnected unexpectedly",           → becomes →  {"category": "SESSION_DISCONNECT", "action": "use recovery_protocol to reconnect"}
        "agent crashed during execution",              → becomes →  {"category": "AGENT_CRASH", "action": "restart agent session, check logs"}
    ]
    
    for raw in ["run error: unknown", "run timeout exceeded", "session disconnected unexpectedly", "agent crashed during execution"]:
        result = classify_error(raw)
        print(f"  '{raw}'")
        print(f"    → category={result['category']}")
        print(f"      action={result['action']}")
    
    # Show the full pattern map:
    print("\n  Available ERROR_PATTERNS:")
    for key, desc in list(ERROR_PATTERNS.items())[:5]:
        print(f"    {key}: {desc}")
    
    return result


# ──────────────────────────────────────────────────────────────────────
# 3. Recovery Protocol (recovery_protocol)
# ──────────────────────────────────────────────────────────────────────

from ds_eo_openclaw.run_reliability.recovery_protocol import get_recovery_steps, RecoveryStep

def example_recovery():
    """Get executable recovery steps for a detected orhpahed run."""
    
    print("\n=== Recovery Protocol ===")
    
    # Example: get recovery steps for an orphaned run scenario
    case = "orphaned_run"
    steps = get_recovery_steps(case)
    
    for i, step in enumerate(steps, 1):
        print(f"  Step {i}: [{step['action']}]")
        print(f"    {step['description']}")
        if step.get('precondition'):
            print(f"    Precondition: {step['precondition']}")
        if step.get('expected_outcome'):
            print(f"    Expected outcome: {step['expected_outcome']}")
    
    return steps


# ──────────────────────────────────────────────────────────────────────
# Main — Run all examples
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("DS-EO Run-State Reconciliation Layer — Usage Examples")
    print("=" * 60)
    
    result1 = example_orphaned_detection()
    result2 = example_error_classification()
    result3 = example_recovery()
    
    print("\n" + "=" * 60)
    print("All examples completed.")
    print(f"  Detection results: {len(result1.get('orphaned_runs', []))} orphans found")
    print(f"  Error classification: '{result2['category']}'")
    print(f"  Recovery steps: {len(result3)} steps generated")
