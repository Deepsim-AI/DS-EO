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
| Governance | `approval_protocol.md`, `review_protocol.md`, `GATE_AUTHORITY_MATRIX.md` | Gates, scoring, decision authority, gate governance |
| Communication | `communication_protocol.md` | Message formats and conventions |
| Workflow | `delegation_protocol.md`, `handoff_protocol.md`, `completion_protocol.md`, `release_management_protocol.md` | Task lifecycle management, post-G4 closure, documentation sync |
| Runtime | `source_inspection_protocol.md` | Context pressure prevention, bounded source inspection, model diagnosis |

## Installation Deployment

During DS-EO installation:

1. **Global deployment** (Step 4): All protocol files copied to `~/.openclaw/protocols/`. These become the authoritative source.
2. **Per-project deployment** (Step 5, optional): Protocol files copied to `<project>/docs/development/protocols/` for project-level reference and customization.

## Protocol Reference

| Protocol | Section in AGENTS.md | Layer |
|----------|---------------------|-------|
| `approval_protocol.md` | §4, §10 | Governance |
| `review_protocol.md` | §10 (G3) | Governance |
| `GATE_AUTHORITY_MATRIX.md` | §10 | Governance |
| `communication_protocol.md` | §5 | Communication |
| `delegation_protocol.md` | §3, §4 | Workflow |
| `handoff_protocol.md` | §11 | Workflow |
| `completion_protocol.md` | G4→G5 | Workflow |
| `release_management_protocol.md` | §4 (Post-G4) | Workflow |
| `source_inspection_protocol.md` | §12 | Runtime |

## Rules

1. Global protocols are the source of truth — project adaptations should not contradict them.
2. DS-EO owns its protocol definitions within this package. Installation overwrites existing global copies (with backup).
3. Project-level adaptations are welcome but must be clearly marked as such.
4. Protocol versioning is managed by DS-EO; project adaptations track the DS-EO version they adapt from.
