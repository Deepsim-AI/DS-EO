# Model Pressure Management Reference — DS-EO

**Purpose**: Prevent CPU-only compaction failures by managing Ollama model load.

## Rule: Never Load All 5 Models Simultaneously

All models total ~87GB VRAM on a system with only 61GB RAM. Excess overflows to swap, which kills inference performance and causes compaction timeouts.

## Loading Matrix by Task Phase

| Phase | Active Agents | Required Models | Unloaded | Estimated Load |
|-------|--------------|-----------------|----------|---------------|
| **CTO planning** | CTO only | qwen3.6:35b, nomic-embed-text | gpt-oss:20b, laguna-xs-2.1, ornith:35b | ~22GB |
| **CTO + Implementer** | CTO, Implementer | qwen3.6:35b, ornith:35b, nomic-embed-text | gpt-oss:20b, laguna-xs-2.1 | ~43GB |
| **Reviewer phase** | Reviewer + CTO | laguna-xs-2.1, qwen3.6:35b, nomic-embed-text | ornith:35b, gpt-oss:20b | ~42GB |
| **Full automatic mode** | CTO → Implementer → Reviewer (staggered) | All needed but NOT concurrent | Unload between phase transitions | Stagger, never stack |
| **Idle/waiting** | None active | nomic-embed-text only | qwen3.6:35b, ornith:35b, laguna-xs-2.1, gpt-oss:20b | <1GB |

## Commands

### Check loaded models
```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -c "import json,sys; d=json.load(sys.stdin); [print(m['name'], m.get('size',0)//(1024**3), 'GB') for m in d.get('models',[])]"
```

### Unload a model (safe if not currently in use)
```bash
ollama rm <model_name>
```

### Load a model on demand
```bash
ollama pull <model_name>
```

## Operational Rules

1. **Unload before starting any long-running task** — start with minimal model pressure
2. **Pull needed model only when dispatching an agent**, not ahead of time
3. **Unload immediately after agent completes** its phase
4. **Always keep nomic-embed-text loaded** — it's small (<1GB) and used for memory search
5. **After any compaction timeout, unload one large model** to free RAM for the next attempt

## Hardware Context

| Resource | Value | Impact |
|----------|-------|--------|
| Total RAM | 61 GiB | Hard ceiling |
| Currently used | ~37 GiB (after unloading) | ~24 GB headroom |
| Swap | 30 GiB (unused) | Avoiding swap is critical for performance |
| GPU | None | All inference on CPU — much slower than GPU |

---
*Created as part of TASK_DS_EO_033 fix.*
