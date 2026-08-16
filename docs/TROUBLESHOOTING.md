# Troubleshooting — DS-EO + OpenClaw

Diagnoses, root causes, and fixes for known operational issues.

> **For new users**: read [Context Window & Compaction Sizing](#context-window--compaction-sizing) first — it covers the #1 source of "agent can't work" complaints.

---

## Context Window & Compaction Sizing

### Symptom

Agent session "overflow" errors, `Context overflow: prompt too large`, `livenessState=blocked`, compaction failure, or the agent appears stuck / unresponsive despite a fresh session. The user creates a new session but hits the same wall.

### Root causes (in order of impact)

1. **`contextWindow` in `openclaw.json` exceeds the model's actual limit.**
   OpenClaw's global default is `contextWindow: 262144` (262K). If the underlying model (e.g., `gpt-oss:20b` served via Ollama) only supports **128K** (`131072`), the session budget is computed against 262K but the real model hard-limits at 128K. Any session that accumulates ~100K+ tokens of history + bootstrap context will overflow the real limit even though OpenClaw believes there is room.

2. **Compaction keeps too much history relative to the real window.**
   With `keepRecentTokens: 120000` and a 128K real window, post-compaction state (kept tokens + summary + bootstrap) exceeds the window. The next inference request overflows and `qualityGuard` fails after `maxRetries: 1`.

3. **Compaction timeout too short for slow inference.**
   Compaction itself is an inference call. On CPU or memory-constrained hardware, `timeoutSeconds: 300` is too short and the compaction aborts mid-stream.

4. **Multiple large models resident simultaneously.**
   Each agent role loads a model into RAM/VRAM (27B ≈ 17GB, 35B ≈ 20GB, 20B ≈ 12GB). With 5 roles, the sum can exceed available memory and spill to swap. Inference (including compaction) slows down and times out. See AGENTS.md §3.5 for the model-pressure table.
### Root cause 5: Unregistered models in `openclaw.json` model list

**Symptom**: Agent works poorly or fails for models that were never added to the
`models.providers.ollama.models` array — e.g., the Implementer (`qwen3.8:27b`)
or PM (`gpt-oss:20b`). OpenClaw falls back to internal defaults for those models,
which may not match Ollama's actual context_window, and `num_ctx` is never passed.

**Why this happens**: The `openclaw.json` model registry only needs entries for models
that differ from OpenClaw's defaults — but **every model used by an agent must have a
complete entry** (id, contextWindow, maxTokens, params.num_ctx). Models that are loaded
dynamically via their agent model string (e.g., `ollama/qwen3.8:27b`) and have NO
registry entry get zeroed-out metadata from OpenClaw's defaults. This silently breaks
token budgeting, compaction sizing, and gateway validation.

**Diagnosis**: Check which models are actually registered:

```bash
python3 << 'EOF'
import json
with open('/home/deepsim/.openclaw/openclaw.json') as f:
    d = json.load(f)

registered = set()
for m in d.get('models',{}).get('providers',{}).get('ollama',{}).get('models',[]):
    registered.add(m['id'])
    ctx = m.get('contextWindow','NOT_SET')
    mt = m.get('maxTokens','NOT_SET')
    nc = m.get('params',{}).get('num_ctx','NOT_SET')
    print(f"  {m['id']}: contextWindow={ctx}, maxTokens={mt}, num_ctx={nc}")

print()
for a in d.get('agents',{}).get('list',[]):
    mid = a.get('model','').split('/')[-1] if '/' in a.get('model','') else a.get('model','')
    status = 'OK' if mid in registered else '⚠️  NOT REGISTERED'
    print(f"  Agent {a['id']}: model={mid} -> {status}")
EOF
```

Compare against `ollama show <model> | grep context length` for each agent's model.
Any mismatch or missing registration is a bug.

**Fix**: Add every model that appears in any agent's `model` field to the registry with
its real `contextWindow`, `maxTokens`, and `params.num_ctx`:

```jsonc
// models.providers.ollama.models — add entries for ALL models used by agents
{
  "id": "qwen3.8:27b",         // Implementer model
  "contextWindow": 262144,
  "maxTokens": 8192,
  "params": { "num_ctx": 262144 }
},
{
  "id": "gpt-oss:20b",          // PM model
  "contextWindow": 131072,       // Ollama reports this — NOT 262K!
  "maxTokens": 8192,
  "params": { "num_ctx": 131072 }
}
```

**Post-fix steps**: After adding entries, restart gateway (`openclaw gateway restart`) and
reset any broken sessions with `/reset`. Verify with `openclaw status` — all sessions should
show < 80% of window.


### Diagnosis steps

Run these from the gateway host:

```bash
# 1. Check the real context window each model actually supports
ollama ps                          # CONTEXT column = real limit per loaded model
ollama show <model> | head -30     # model card metadata

# 2. Check what OpenClaw believes the window is
python3 - <<'EOF'
import json
d = json.load(open('/home/deepsim/.openclaw/openclaw.json'))
for m in d.get('models',{}).get('providers',{}).get('ollama',{}).get('models',[]):
    print(f"{m['id']}: configured={m.get('contextWindow')}")
print("compaction:", d.get('agents',{}).get('defaults',{}).get('compaction',{}))
EOF

# 3. Check current session usage vs window
openclaw status                     # Tokens column shows usage/window per session

# 4. Check memory pressure
free -h
cat /proc/loadavg
```

A session is "broken" when `Tokens` column shows usage > 100% of window.

### Fix — config values that work with a gpt-oss:20b (128K real window) model

Apply to `~/.openclaw/openclaw.json`:

```jsonc
{
  "models": {
    "providers": {
      "ollama": {
        "models": [
          {
            "id": "gpt-oss:20b",
            "contextWindow": 131072          // MUST match `ollama show | grep context length` (131072)
            // ...
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "compaction": {
        "keepRecentTokens": 50000,           // post-compaction history budget
        "reserveTokensFloor": 24000,         // headroom for bootstrap + new work
        "timeoutSeconds": 600,               // compaction inference budget
        "mode": "safeguard",
        "truncateAfterCompaction": true,
        "maxActiveTranscriptBytes": "10mb",
        "maxHistoryShare": 0.5,
        "midTurnPrecheck": { "enabled": true },
        "notifyUser": true,
        "qualityGuard": { "enabled": true, "maxRetries": 1 }
      }
    }
  }
}
```

**Sizing rule of thumb** (for any model with real window `W`):

| Setting | Formula | Rationale |
|---|---|---|
| `contextWindow` | = real model limit | OpenClaw must budget against reality |
| `keepRecentTokens` | ≈ `W * 0.40` | leaves room for summary + bootstrap + new work |
| `reserveTokensFloor` | ≈ `W * 0.18` | bootstrap context (AGENTS.md, skills, memory) |
| `timeoutSeconds` | ≥ `600` if CPU or shared GPU | compaction is itself an inference call |

For a 128K window: `50000 + 24000 ≈ 74K` post-compaction baseline, leaving ~54K for new work. For a 262K window: ~105K + ~47K, leaving ~110K.

### Applying the fix

1. Back up: `cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak-$(date +%s)`
2. Edit as above (or use the `gateway` tool's `config.patch` if available).
3. Restart: `openclaw gateway restart`
4. Reset broken sessions (one per chat): type `/reset` in that session.
5. Verify: `openclaw status` should show all sessions under 100% of window.

### Related AGENTS.md rules

- **R-SI-1** (never read large files wholesale) — reduces single-turn token spikes
- **R-SI-3** (stop on compaction failure) — what agents should do when this happens
- **R-SI-5** (model replacement is not the first response) — diagnose context pressure before swapping models
- **R-SI-6** (separate implementation from documentation) — avoid one session doing both
- **§3.5 Model Pressure Management** — max 3 large models resident simultaneously

---

## Recovering a broken session

A session is **broken** when `openclaw status` shows its Tokens column > 100% of the window (e.g., `518k / 262k`). The session cannot accept new input effectively; compaction will fail; the model will return truncated or empty responses.

**Recovery:**

1. Apply the config fix above (if not already done) and restart the gateway.
2. In the broken chat, send `/reset` — this clears the session's transcript and starts fresh.
   - You cannot send `/reset` from inside an agent session; it must come from the user in that chat.
   - Alternatively, archive the session via `sessions_list` → archive action, then start a new one.
3. Before closing any in-progress work in the broken session, have the agent persist artifacts to the task directory (`docs/development/reports/TASK_<id>/`) — session memory is lost on reset.

**Prevention:**

- Keep `keepRecentTokens` ≤ 40% of the real window
- Don't run CTO + Implementer + Reviewer concurrently (each loads a 17–20GB model)
- Watch `openclaw status` during long tasks; reset proactively at ~80% window usage

---

## Quick reference

| Symptom | First check | Fix |
|---|---|---|
| Agent works poorly (Implementer/PM specifically) | Run the "Root cause 5" diagnosis script — are all agent models registered? | Add missing models to `models.providers.ollama.models` with full config |
| Model used by agent has wrong `contextWindow` | `ollama show <model> | grep context length` vs config value | Set `contextWindow` and `params.num_ctx` to match |
| `Context overflow: prompt too large` | `ollama ps` CONTEXT column vs config `contextWindow` | Set `contextWindow` = real limit |
| Compaction fails mid-stream | `timeoutSeconds` in `agents.defaults.compaction` | Raise to ≥ 600s |
| Agent "stuck" after compaction | `keepRecentTokens` + `reserveTokensFloor` vs real window | Reduce to ≤ 40% / ≤ 18% of window |
| Multiple agents slow at once | `free -h`, `ollama ps` (resident model count) | Unload idle models; max 3 concurrent |
| New session also overflows | Bootstrap context size (AGENTS.md + skills + memory) | Trim AGENTS.md; disable unused skills |
| Session at 500%+ of window | Already broken; `/reset` required | `/reset` in that chat |

---

*Last updated: 2026-08-15. Owner: DS-EO engineering org. Related: AGENTS.md §3.5, `protocols/source_inspection_protocol.md`.*
