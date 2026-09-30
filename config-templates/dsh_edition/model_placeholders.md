# Model Placeholder Reference

DS-EO uses four agent models with placeholders in configuration files. Replace each placeholder before deployment.

| Placeholder | Agent | Description | Recommended Model |
|------------|-------|-------------|-------------------|
| `<MODEL_CTO>` | CTO / Architect 🏗️ | Architecture review, task planning | `ollama/qwen3.6:35b` |
| `<MODEL_IMPLEMENTER>` | Code Implementer 💻 | Implementation of approved plans | `ollama/qwen3.8:27b` |
| `<MODEL_REVIEWER>` | Senior Code Reviewer 🔍 | Independent code verification | `ollama/laguna-xs-2.1:q4_K_M` |
| `<MODEL_PM>` | Project Manager 📋 | Process oversight, task lifecycle | `ollama/ornith-1.5:35b` |

## Updating Models in openclaw.json

In `config-templates/dsh_edition/openclaw.json`, each agent entry has a `"model"` field.
Replace the placeholder with your chosen model:

```jsonc
{
  "id": "cto",
  "model": "ollama/qwen3.6:35b",  // was <MODEL_CTO>
}
```

## Pulling Models

Before starting, pull all models locally:

```bash
ollama pull qwen3.6:35b
ollama pull qwen3.8:27b
ollama pull laguna-xs-2.1:q4_K_M
ollama pull ornith-1.5:35b
```

## Hardware Constraint (Jetson Orin)

All five models total ~87GB unified memory. Never load all simultaneously — use only 3 at a time per phase. See AGENTS.md §3.5 for compaction-aware session management.

