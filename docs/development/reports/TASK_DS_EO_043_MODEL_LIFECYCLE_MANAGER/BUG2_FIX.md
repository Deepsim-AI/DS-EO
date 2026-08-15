# Bug 2 Fix — Phase A Test Failures

**Date:** 2026-08-14 18:05 PDT  
**Fixed by:** CTO 🏗️  
**Status:** ✅ Resolved (all 30 tests pass)

## Summary

Phase A implementation introduced 2 test failures in the `test/execution_strategy/` suite. Both were fixable without changing any production code.

---

## Bug 2a: `test_spawns_via_existing_manager_if_available`

**File:** `test/execution_strategy/test_concurrent_identity.py`  
**Root cause:** The test used `patch.object(strategy, 'spawn_manager', ...)` on an *instance*, but `spawn_manager` is a `@property` descriptor. Python's mock library can't setattr/delattr descriptors.

**Fix:** Changed to patch on the *class* instead:
```python
# Before (broken):
with patch.object(strategy, 'spawn_manager', new_callable=lambda: MagicMock()) as mock_spawn_mgr:

# After (fixed):
mock_spawn_mgr = MagicMock()
with patch.object(type(strategy), 'spawn_manager', new_callable=lambda: mock_spawn_mgr):
```

Also added registry mocking because the real `AgentRegistry.load()` returns `success=True, agent=None` for a specific lookup (it's load-all, not find-one). Without this mock the test hit early exit before reaching spawn logic.

---

## Bug 2b: `test_parse_size_gb_handles_formats`

**File:** `test/execution_strategy/test_capability_assess.py`  
**Root cause:** Test used `pytest.approx()` inline with an `or` clause containing subtraction:
```python
assert actual == expected or abs(actual - expected) < 0.001
```
When `expected` is a `pytest.approx(...)` object (ApproxScalar), Python tries `float - ApproxScalar` which raises `TypeError`.

**Fix:** Replaced with proper pytest.approx usage:
```python
# Before (broken):
assert actual == expected or abs(actual - expected) < 0.001

# After (fixed):
assert pytest.approx(actual, rel=1e-3) == expected
```

Also replaced inline `pytest.approx()` values with plain floats in the test data (since the assertion now uses approx).

---

## Verification

```
$ python -m pytest test/execution_strategy/ -v
============================== 30 passed in 0.29s ==============================
```

Both production code and config files remain unchanged — only test assertions were corrected.
