# CTO_PLAN.md — TASK_DS_EO_DSH_012

**Task:** Phase 8B: Deployment Documentation  
**Author:** CTO (qwen3.6:35b)  
**Date:** 2026-09-30  
**Gate:** G1 — Plan for User Review  

---

## 1. Objective

Produce comprehensive deployment documentation for DS-EO DSH Edition, enabling anyone to set up, configure, and run the system with a real DSH API endpoint.

---

## 2. Scope: Four Deliverables

### Deliverable B1: `.env.example` (Minimal Environment File)

The single entry point for environment configuration. Lists all required/optional variables with descriptions and defaults.

```bash
# DS-EO DSH Edition — Environment Configuration
DSH_API_BASE=                # Required: DeepSeek Harness API base URL
DSH_API_TOKEN=               # Optional: Bearer token for authentication
OLLAMA_HOST=localhost:11434  # Optional: Ollama endpoint for fallback models
WORKSPACE_ROOT=/path/to/ds_eo_dsh  # Optional: workspace root path
LOG_LEVEL=INFO               # Optional: DEBUG, INFO, WARNING, ERROR (default: INFO)
```

### Deliverable B2: `DEPLOYMENT_GUIDE.md` (Comprehensive Setup Guide)

Multi-section deployment document covering:

| Section | Content |
|---------|---------|
| Prerequisites | Python 3.10+, Ollama or compatible model server, DSH API access |
| Quick Start | `.env.example` setup → `pip install -r requirements.txt` → run |
| Environment Setup | Detailed explanation of each env var in `.env.example` |
| DSH Endpoint Configuration | How to configure `DSH_API_BASE` for production vs dev |
| Agent Model Configuration | Updating model placeholders (`<MODEL_CTO>`, etc.) for your models |
| OpenClaw Integration | When and how to run DS-EO within an OpenClaw environment (Path A) vs standalone (Path B) |
| Security Notes | Token management, network security, sandboxing |

### Deliverable B3: `config-templates/dsh_edition/` (Production Config Directory)

New directory with DSH-specific agent configuration templates:

| File | Purpose |
|------|---------|
| `openclaw.json` | Full OpenClaw config with DSH Edition agent definitions, updated model placeholders, DSH-aware tool settings |
| `agents.list.yaml` | Simplified agent list for manual openclaw agents add |
| `model_placeholders.md` | Reference document for each agent's model placeholder and how to replace it |

### Deliverable B4: `UPGRADE_FROM_OPENCLAW_EDITION.md` (Migration Guide)

Step-by-step migration from the old `ds_eo_openclaw/` edition to `ds_eo_dsh/`:

1. Verify current commit (e3760a2+)
2. Update config templates with new package name references
3. Update `.env.example` if creating fresh env file
4. Test run with DSH endpoint configured

---

## 3. Files Changed

| Action | File | Type |
|--------|------|------|
| NEW | `ds_eo_dsh/.env.example` | Env template |
| NEW | `DEPLOYMENT_GUIDE.md` (project root) | Comprehensive deployment docs (~200 lines) |
| NEW | `UPGRADE_FROM_OPENCLAW_EDITION.md` | Migration guide (~60 lines) |
| NEW | `config-templates/dsh_edition/openclaw.json` | Production config template (~150 lines) |
| NEW | `config-templates/dsh_edition/model_placeholders.md` | Model placeholder reference (~30 lines) |
| MODIFIED | `README.md` | Update to reflect ds_eo_dsh package name and DSH Edition branding |

---

## 4. Acceptance Criteria by Gate

### G2 (Execution Ready)
- [x] CTO_PLAN.md complete with all deliverables scoped
- [x] All env vars identified from codebase inspection

### G3 (Review Complete)
- [ ] `.env.example` covers all DSH-related environment variables
- [ ] `DEPLOYMENT_GUIDE.md` covers all deployment paths (standalone, OpenClaw integration)
- [ ] Config templates use updated package name references
- [ ] Migration guide is complete

### G4 (CTO Approval Ready)
- [ ] All deliverables produced
- [ ] No outdated references to `ds_eo_openclaw` in deployment docs
- [ ] Config templates are functional (can be copied and used directly)

---

## 5. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Docs become stale when new env vars are added | Low | Add "See `.env.example` for complete list" cross-reference |
| Config template doesn't match actual openclaw.json format | Medium | Base config on current openclaw.json structure (verified) |
| Migration guide misses edge cases | Medium | Cover all 4 common migration scenarios |

---

## 6. Pending Decisions

1. **Ready for Phase 8B execution?** Signal when approved.

