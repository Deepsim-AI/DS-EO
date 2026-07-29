# DS-EO Protocol Hierarchy Guide

## Protocol Layers

DS-EO protocols exist in two layers, following a global-to-project hierarchy:

```
Layer 1: Global Standards (authoritative)
    ~/.openclaw/protocols/*.md
    
Layer 2: Project Adaptations (optional)
    <project>/docs/development/protocols/*.md
```

## How It Works

- **Global protocols** (`~/.openclaw/protocols/`) are the authoritative source of truth. DS-EO deploys its own copies here during installation.
- **Project adaptations** are optional per-project mirrors that can add project-specific context, examples, or overrides. They should never contradict global standards.

## Protocol Categories

| Category | Protocols | Purpose |
|----------|-----------|---------|
| Governance | `approval_protocol.md`, `review_protocol.md` | Gates, scoring, decision authority |
| Communication | `communication_protocol.md` | Message formats and conventions |
| Workflow | `delegation_protocol.md`, `handoff_protocol.md`, `completion_protocol.md` | Task lifecycle management |

## Installation Deployment

During DS-EO installation:

1. **Global deployment** (Step 4): All protocol files copied to `~/.openclaw/protocols/`. These become the authoritative source.
2. **Per-project deployment** (Step 5, optional): Protocol files copied to `<project>/docs/development/protocols/` for project-level reference and customization.

## Rules

1. Global protocols are the source of truth — project adaptations should not contradict them.
2. DS-EO owns its protocol definitions within this package. Installation overwrites existing global copies (with backup).
3. Project-level adaptations are welcome but must be clearly marked as such.
4. Protocol versioning is managed by DS-EO; project adaptations track the DS-EO version they adapt from.
