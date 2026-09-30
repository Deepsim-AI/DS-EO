# Model Management Protocol — DS-EO

**Purpose**: Govern how models are added, removed, unloaded, or replaced across the OpenClaw gateway. Prevent accidental agent breakage from orphaned model dependencies.

---

## Core Rules

### Rule 1: No Agent May Delete Models Without User Confirmation

**Agents MUST NEVER delete (`ollama rm`) any model without explicit user confirmation.** Even if an agent has the capability or sees a need to free memory, deleting models is a privileged operation that affects all agents' runtime state.

**Prohibited actions (no exceptions):**
- `ollama rm <model>` — even idle models
- `ollama delete <model>`
- Any command that removes model weights from disk

### Rule 2: User Confirmation Required for Model Changes

Before removing or significantly modifying any model configuration, the agent MUST:
1. **State clearly** which model will be affected and why
2. **Describe the impact** on which agents depend on it (e.g., "Removing `ornith-1.5` will disable the PM agent")
3. **Ask for explicit confirmation** — e.g., "Do you confirm removing `ornith-1.5:35b`?"

### Rule 3: Model Additions Also Require Verification

When adding models to the OpenClaw registry (`openclaw.json` → `models.providers.ollama.models`):
- Verify the model actually exists on disk first (`ollama list | grep <model>`)
- Verify the real context window matches what you're configuring (`ollama show <model> | grep 'context length'`)
- Add complete entry with all four required fields: `id`, `contextWindow`, `maxTokens`, `params.num_ctx`
- Restart the gateway after changes (`openclaw gateway restart`)

### Rule 4: Model Registry Must Always Match Agent Dependencies

Every model referenced in an agent's `model` field MUST have a corresponding entry in `models.providers.ollama.models`. Check with:

```bash
python3 << 'EOF'
import json
with open('/home/deepsim/.openclaw/openclaw.json') as f:
    d = json.load(f)

registered = set()
for m in d.get('models',{}).get('providers',{}).get('ollama',{}).get('models',[]):
    registered.add(m['id'])

for a in d.get('agents',{}).get('entries', {}):
    mid = a.get('model','').split('/')[-1] if '/' in a.get('model','') else a.get('model','')
    status = 'OK' if mid in registered else '⚠️  NOT REGISTERED'
    print(f"Agent {a['id']}: {mid} -> {status}")
EOF
```

### Rule 5: Memory Pressure Management — The Safe Way

When concerned about memory pressure:
1. **Unload (not delete)** idle models: `ollama unload <model>` — this frees VRAM/RAM but keeps weights on disk
2. **Verify** the model still exists on disk before considering deletion
3. **Check which agents depend** on each model before removing it

The correct sequence for freeing memory:
```bash
# Safe: unload (reversible, free from Ollama)
ollama unload <model-name>

# Only after user confirmation and checking dependencies
ollama rm <model-name>  # DESTRUCTIVE — must ask first
```

---

## Common Mistakes to Avoid

| Mistake | Consequence | How to Prevent |
|---------|-------------|----------------|
| Unloading a model the agent needs right now | Agent session fails or degrades | Check `ollama ps` before unloading |
| Deleting a model still in config registry | Root Cause 5: agent breaks silently | Run the verification script above after any rm |
| Removing a model without checking agents | PM, Reviewer, etc. may break | Always run dependency check first |
| Setting wrong `contextWindow` in registry | Compaction fires at wrong intervals | Match `ollama show | grep context length` exactly |

---

## References

- Root Cause 5: [TROUBLESHOOTING.md](../TROUBLESHOOTING.md#root-cause-5) — Unregistered models
- Model pressure: [AGENTS.md §3.5](../AGENTS.md#model-pressure-management)
- Agent dependency check: Use the verification script in Rule 4

---

**Effective**: Immediately upon creation  
**Owner**: All agents  
**Review frequency**: Every TASK where model changes occur
