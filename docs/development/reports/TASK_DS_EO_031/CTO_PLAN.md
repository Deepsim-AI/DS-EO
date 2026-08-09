---
produced_by: ollama/qwen3.6:35b
role: CTO
task_id: TASK_DS_EO_031
generated_at: 2026-08-08T02:48:00Z
gate: G1
---

# TASK_DS_EO_031 — Upstream bug/patch: resolveSessionModelRef precedence between per-agent config and stale session metadata

## Problem Statement

`openclaw status` displays the **default** model for every agent instead of each agent's configured per-agent model. This is caused by a precedence bug in `resolveSessionModelRef`: it gives persisted session-entry model values higher priority than current per-agent configuration. Once a session entry is created with any model, that value persists indefinitely in the display — even if the agent config later changes to a different model.

Runtime model routing is unaffected (confirmed via logs and trajectory files). The bug is purely in the status/display lookup path.

---

## Root Cause Analysis

### 1. Stale session entry writes first, never updates on config change

When an agent's first session is created, `sessions.json` populates every entry with the model resolved at that moment — which for PM was `qwen3.6:35b` (the default). Later changing the agent config to `gpt-oss:20b` does **not** update existing session entries.

### 2. `resolveSessionModelRef` priority order is inverted

Source: `status.summary-fItK9afs.js` → `resolveSessionModelRef()`

Priority order in current code:
1. `providerlessPersisted` — uses `entry.modelOverride/entry.modelOverrideSource` (skipped if no value)
2. **`resolvePersistedSelectedModelRef(runtimeProvider=entry.modelProvider, runtimeModel=entry.model)`** — returns the stale session entry model immediately
3. Falls through to `resolveConfiguredStatusModelRef(agentId=...)` which would return the correct per-agent config model

**The bug:** Step 2 returns a non-null value from stale session data *before* step 3 is reached, so the agent-config-derived model is never consulted for display.

### 3. The fix must address the precedence contract

The question `resolveSessionModelRef` should answer is: *"What is this session's effective model?"* There are two valid interpretations:

| Interpretation | Meaning | Correctness |
|---|---|---|
| A (current) | "What model was *actually used* when this session ran" | Accurate for historical record, but misleading for display if config changed |
| B (desired) | "What model does this agent *currently use*, per its configuration" | Correct for status/TUI — shows current intent, not historical artifact |

For status/display purposes, **B is the correct interpretation**. If a user changes an agent's model in config, they expect to see it reflected immediately.

---

## Proposed Patch (Upstream Bug Report + Fix)

### File(s) affected
- `src/commands/status.summary.ts` (TypeScript source; compiled to `status.summary-fItK9afs.js`)
- Specifically the `resolveSessionModelRef()` function

### Change: Correct precedence in `resolveSessionModelRef`

**Current logic:**
```ts
function resolveSessionModelRef(cfg, entry, agentId) {
  const resolved = resolveConfiguredStatusModelRef({ cfg, defaultProvider, defaultModel, agentId });
  // ...
  const providerlessPersisted = /* ... */;
  if (providerlessPersisted) return providerlessPersisted;

  return resolvePersistedSelectedModelRef({
    defaultProvider,
    runtimeProvider: entry?.modelProvider,   // ← stale session value!
    runtimeModel: entry?.model,              // ← stale session value!
    overrideProvider: entry?.providerOverride,
    overrideModel: entry?.modelOverride,
    ...
  }) ?? resolved;  // ← NEVER REACHED for PM because step above returns non-null
}
```

**Proposed logic:**
```ts
function resolveSessionModelRef(cfg, entry, agentId) {
  const resolved = resolveConfiguredStatusModelRef({ cfg, defaultProvider, defaultModel, agentId });
  
  // If there's a user-pinned model override (explicit /model change), use it.
  if (hasUserPinnedModelSelection(entry)) {
    return resolvePersistedSelectedModelRef({...});
  }

  // Check if the session's runtime model matches the agent config.
  // If they match, return it (for display consistency with "what this session ran on").
  const persisted = resolvePersistedSelectedModelRef({
    defaultProvider: resolved.provider || "openai",
    runtimeProvider: entry?.modelProvider,
    runtimeModel: entry?.model,
    overrideProvider: entry?.providerOverride,
    overrideModel: entry?.modelOverride,
    ...
  });

  if (persisted) {
    // If the persisted model matches the config, return it (normal case).
    if (areRuntimeModelRefsEquivalent(persisted, resolved)) {
      return persisted;
    }
    // If they differ AND no user override exists:
    // The config is the source of truth — the session entry is stale.
    // Invalidate it by returning the config value.
  }

  return resolved;  // Agent config wins when session entry is stale/no-override
}
```

### Alternative approach (simpler): Invalidating stale entries on startup

Instead of changing lookup logic, add a migration step during gateway startup:

1. For each agent in `agents.list`, compare `agent.model` against every session entry's `model`
2. If they differ AND no `modelOverrideSource === "user"` exists, update the session entry to match the config
3. This ensures persistence stays in sync with configuration

This is safer (less logic change) but requires iterating all sessions on startup.

### Alternative approach (least invasive): Use modelOverrideSource

In `resolvePersistedSelectedModelRef`, only return a value if:
- `modelOverrideSource === "user"` (explicit user override), OR  
- The persisted model matches the per-agent config for that agent

This preserves backward compatibility while fixing the stale-display bug.

---

## Deliverables

1. **Bug report** — File against OpenClaw repo with reproduction steps, root cause analysis, and proposed fix
2. **Patch proposal** — TypeScript diff of `resolveSessionModelRef` with all three approaches evaluated
3. **Local workaround script** (optional) — Auto-detect-and-fix stale session entries on demand
4. **Acceptance verification** — Confirm `openclaw status` shows correct per-agent models after fix

## Acceptance Criteria

1. Per-agent model configuration in `agents.list[].model` takes precedence over persisted session entry `model` for all display/logic paths that read "effective model"
2. Stale session metadata is either: (a) invalidated on config change, or (b) ignored when it differs from config and no user override exists
3. User-pinned overrides (`/model`, `modelOverrideSource === "user"`) still take precedence over config — user intent must not be overridden by automatic sync
4. Runtime model routing for CTO, Implementer, Reviewer, PM is unchanged
5. No session metadata corruption or data loss

## Implementation Notes

- **Do NOT change runtime model resolution** — only the status/display lookup path
- **Preserve backward compatibility** — user-pinned overrides must still work
- The `areRuntimeModelRefsEquivalent()` function already exists in this codebase (imported from `model-runtime-aliases-w4oRlOM0.js`) and can be reused for comparison
- Consider adding a migration/version field to session entries so future stale-value bugs are detected automatically

## Verification Steps

1. Before: confirm `openclaw status` shows incorrect models for agents whose config changed after initial creation
2. Apply patch → restart gateway
3. After: verify each agent displays its configured model
4. Test edge cases: user-pinned override, fresh session, config rollback
5. Confirm no regression on runtime model selection via logs and trajectory files
