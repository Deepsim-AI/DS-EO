# DS-EO Compatibility Matrix

## OpenClaw Version Compatibility

| DS-EO Version | Minimum OpenClaw Version | Notes |
|---------------|-------------------------|-------|
| 0.1.x (current) | 2026.7.1 | Tested on 2026.7.1 and later |
| 0.2.x (planned) | TBD | Self-hosting edition |
| 1.0.x (planned) | TBD | Platform abstraction layer |

## Agent Model Compatibility

DS-EO is platform-agnostic at the protocol level. The only model-specific aspect is the `model` field in agent config entries. Any model supported by your OpenClaw provider should work.

### Tested Models

| Role | Model | Provider | Status |
|------|-------|----------|--------|
| CTO | `ollama/qwen3.6:35b` | Ollama | ✓ Tested |
| Implementer | `ollama/ornith:35b` | Ollama | ✓ Tested |
| Reviewer | `ollama/laguna-xs-2.1:q4_K_M` | Ollama | ✓ Tested |

### Recommended Alternatives

Any model with sufficient context window and instruction-following capability can substitute. Consider:
- **CTO**: Models strong at planning and analysis (≥35B parameters recommended)
- **Implementer**: Models good at code generation (any coding-focused model)
- **Reviewer**: Models good at critical analysis and verification

## Platform Compatibility

| Component | OpenClaw | Claude Code | Codex | Gemini CLI |
|-----------|:--------:|:-----------:|:-----:|:----------:|
| Agent config format | ✓ Native | ✗ (future adapter) | ✗ (future) | ✗ (future) |
| Protocol system | ✓ Native | ✗ | ✗ | ✗ |
| Task workflow | ✓ Native | ✗ | ✗ | ✗ |

DS-EO v0.1 targets OpenClaw exclusively. Multi-platform support requires the planned abstraction layer (v1.0).

## Troubleshooting Compatibility Issues

### "Agent fails to start"

- Verify model is installed: `ollama list`
- Check model name matches exactly (case-sensitive)
- Ensure sufficient GPU/CPU resources for model size

### "Protocol files not found"

- DS-EO protocols deploy to `~/.openclaw/protocols/` (global) and `<project>/docs/development/protocols/` (per-project)
- Agent prompts reference protocols by filename only — path is resolved at runtime

### "Config merge failed"

- Ensure your `openclaw.json` is valid JSON before installing
- Check disk space (>50MB free)
- Try manual installation following INSTALLATION.md Step-by-step
