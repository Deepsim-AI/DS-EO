# DS-EO OpenClaw Edition — Release Notes


## v0.3.0 — Dispatcher Session Bridge Infrastructure 🔧 (Released 2026-08-05)

### Breaking Fix: spawn_agent() No Longer Returns Mock Success

**Critical infrastructure fix** — the Dispatcher's `spawn_agent()` now creates **real OpenClaw agent sessions** with automatic verification. Previous behavior returned mock success without creating any session, which was a critical reliability defect discovered during TASK_DAL_002.

### What Changed
- Added `dispatcher/session_dispatch/bridge.py` — real session creation via OpenClaw's gateway/session mechanisms
- Added `dispatcher/session_dispatch/verify.py` — automatic session existence/status verification
- Updated `SessionDispatcher.spawn_agent()` to use bridge + verification
- Updated `check_completion()` to query real session status

### Reliability Impact
- Dispatcher now distinguishes real sessions from mock responses automatically
- Every spawn operation is verified before returning success
- TASK_DAL_002 and all future automatic-mode tasks are unblocked (pending host verification)

### Config Fix (also included)
- Fixed `bindings[*].peer.kind` from invalid `"command"` to valid `"direct"` in `.openclaw/openclaw.json`

**Version**: 0.2.0  
**Release Date**: July 31, 2026  
**Author**: Dr. Shouke Wei (魏守科), Founder & CTO  
**Repository**: [github.com/Deepsim-AI/DS-EO](https://github.com/Deepsim-AI/DS-EO)

---

## Executive Summary

DS-EO v0.2.0 marks a significant milestone in the evolution of our engineering organization framework. This release introduces full Windows support via native PowerShell installers, completes protocol and governance consistency across all 14 agent roles (now four official roles: CTO, Implementer, Reviewer, PM), and establishes the complete Post-G4 lifecycle — including Git persistence and GitHub remote push automation.

DS-EO is a **reusable engineering organization framework** that transforms an AI agent platform into a disciplined, gate-governed software engineering team. The OpenClaw Edition (v0.2.0) is the first platform-specific implementation.

---

## What's New in v0.2.0

### 1. Windows Support (NEW)

The installer suite now runs natively on Windows via PowerShell:

- **`install.ps1`** — Full interactive installer mirroring the bash version
- **`verify_installation.ps1`** — Post-install verification with color-coded results
- **`deploy_protocols.ps1` / `deploy_agents.ps1`** — Protocol and prompt deployment
- **`generate_openclaw_config.ps1`** — Agent configuration generation (Python-powered)
- **`conflict_check.ps1`** — Pre-install conflict detection

Windows users can now install DS-EO with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

*(WSL2 remains the recommended path for full bash compatibility.)*

### 2. PM Role Formalization (NEW)

The Project Manager role is now a first-class governance entity, defined in four locations:

- **`AGENTS.md`** Section 3 — Full role definition with model, tool policy, and responsibilities
- **`protocols/completion_protocol.md`** — Post-G4 completion checklist including Git commit and push
- **`protocols/handoff_protocol.md`** — Transition 0b (PM→Close) with remote push step
- **`GATE_AUTHORITY_MATRIX.md`** — Gate G5 (Complete → Closed) owned by PM

The PM now manages:
1. Task detection and CTO task creation requests
2. Artifact integrity verification at every phase transition
3. Post-G4 completion (status updates, changelog entries, PM_CLOSED notifications)
4. Git commit of approved work after each G4 closure
5. GitHub remote push (after explicit user confirmation of target repo + branch)

### 3. Governance Cleanup & Consistency (TASK_DS_EO_015+017)

Protocol authority was audited against actual workflow, resolving:

- Seven protocol inconsistencies (P1–P7 from WORKFLOW_AUDIT)
- Five artifact ownership gaps
- Eight actionable recommendations implemented
- `GATE_AUTHORITY_MATRIX.md` created as the single source of truth for gate governance
- All agent role definitions aligned with actual tool capabilities

### 4. Documentation Consistency Sweep (TASK_DS_EO_018)

A systematic sweep across 10+ documentation files corrected stale references to the pre-migration state:

- PM 📋 added to all roles tables (README, ARCHITECTURE, INSTALLATION)
- Protocol count updated from 6→8 everywhere
- Reviewer tool policy annotations corrected (write allowed for REVIEW_REPORT.md)
- `GATE_AUTHORITY_MATRIX.md` registered in `ds_eo_manifest.yaml` and test expectations

All 53 verification tests pass.

---

## Governance Updates

### New Gate: G5 — Complete → Closed

The Five Gates workflow is now complete:

| Gate | From → To | Authority |
|------|-----------|-----------|
| G1 | Planning → Implementation | User (approves CTO plan) |
| G2 | Implementation → Review | Implementer + CTO confirms |
| G3 | Review → Approval | Reviewer recommends → CTO confirms |
| G4 | Approval → Complete | CTO final decision |
| **G5** | **Complete → Closed** | **PM (Post-G4 admin)** ← NEW |

### Rule Additions to AGENTS.md

- **Rule 6**: CTO must not execute Post-G4 duties — PM handles them exclusively
- All four engineering roles now listed in Section 3 of the governance document

---

## Infrastructure & Security

### Git Remote Push Governance

- PM commits approved work to local Git after each G4 (automated)
- Remote push to GitHub requires **explicit user confirmation** each time
- Credentials stored in `.env` — never committed to version control
- `.gitignore` updated to prevent accidental secret leakage

### Secrets Management

- **`.env.example`** template for SSH keys, GitHub tokens, and Git identity
- **`.gitignore`** blocks `.env`, `secrets/`, `*.key`, `*.pem`, `ssh_keys/`
- Remote repository: `github.com/Deepsim-AI/DS-EO` (SSH auth via Deepsim-AI-Bot account)

---

## What's Coming in v0.2.x

| Area | Planned |
|------|---------|
| Multi-platform editions | Claude, Codex, Gemini variants |
| v1.0 | Platform abstraction layer for cross-platform portability |
| Release management protocol | Automated versioning and release automation |
| Task branching strategy | `task/DS_EO_XXX` branches for G1–G3, merge-to-main at G5 |

---

## Installation

### Linux / macOS / WSL2

```bash
git clone https://github.com/Deepsim-AI/DS-EO.git
cd DS-EO
bash scripts/install.sh
```

### Windows

```powershell
git clone https://github.com/Deepsim-AI/DS-EO.git
cd DS-EO
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

**Prerequisites**: OpenClaw `2026.7.1+`, Python 3.8+, Git

See [INSTALLATION.md](INSTALLATION.md) for detailed steps.

---

## License

MIT  
Copyright (c) 2026 Deepsim Intelligence Technology Inc.

---

*DS-EO is developed and maintained by the Deepsim AI Lab at Deepsim Intelligence Technology Inc.*  
*Dr. Shouke Wei (魏守科), Founder*
