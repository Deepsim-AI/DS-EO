# DS-EO DSH Edition — Deployment Guide

**Package:** `ds_eo_dsh`  
**Version:** 1.0-pre (post Phase 8A)  
**Runtime Requirements:** Python 3.10+, Ollama or compatible model server  

---

## 1. Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | ≥ 3.10 | Required for type hints and async runtime |
| Virtual environment | venv or equivalent | Strongly recommended to avoid dependency conflicts |
| OpenClaw Gateway | Latest stable | For agent session lifecycle management |
| Ollama | ≥ 0.4.x | For local model serving (fallback) |

### Network Requirements

- Access to your DSH API endpoint (`DSH_API_BASE`) from the machine running DS-EO
- If using OpenClaw integration: local `localhost` access to the Gateway port (default 18789)

---

## 2. Quick Start

```bash
# 1. Clone and enter the workspace
git clone <repo-url>
cd ds_eo_dsh

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your environment
cp .env.example .env
# Edit .env to set DSH_API_BASE and DSH_API_TOKEN

# 5. Start OpenClaw Gateway (if using agent integration)
openclaw gateway start

# 6. Run the system
python -m ds_eo_dsh.dispatcher.dispatch
```

---

## 3. Environment Variables

All environment variables are defined in `.env.example`. Here's what each one does:

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DSH_API_BASE` | Base URL for the DeepSeek Harness API. **Set to an empty string or unset to run without DSH API** (all adapter methods return graceful errors). | `https://dsh.example.com/api` |

### Optional — Authentication

| Variable | Description | Default |
|----------|-------------|---------|
| `DSH_API_TOKEN` | Bearer token for DSH API authentication. Used by `DshHttpClient` to set the `Authorization: Bearer <token>` header. | None (unauthenticated requests) |

### Optional — Fallback Models

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_HOST` | Host and port of the Ollama instance. Used when model_info() cannot reach a DSH model catalog. | `localhost:11434` |

### Optional — Runtime Behavior

| Variable | Description | Default |
|----------|-----------|---------|
| `WORKSPACE_ROOT` | Directory where DS-EO stores task artifacts, state, and reports. | Auto-detected from workspace structure |
| `LOG_LEVEL` | Python logging level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`. | `INFO` |

### Setting Environment Variables

**Persistent (recommended):** Create `.env` file in the workspace root (auto-loaded by most frameworks).

```bash
DSH_API_BASE=https://dsh.example.com/api
DSH_API_TOKEN=your-secret-token-here
LOG_LEVEL=DEBUG
```

**Per-session:** Export directly before running.

```bash
export DSH_API_BASE="https://dsh.example.com/api"
export DSH_API_TOKEN="your-secret-token-here"
python -m ds_eo_dsh.dispatcher.dispatch
```

---

## 4. Agent Model Configuration

DS-EO uses four agent models with specific roles. Models are configured in your `openclaw.json` under `agents.list[]`.

| Agent | ID | Default Placeholder | Purpose |
|-------|----|--------------------|---------|
| CTO / Architect 🏗️ | `cto` | `<MODEL_CTO>` | Architecture review, task planning |
| Code Implementer 💻 | `implementer` | `<MODEL_IMPLEMENTER>` | Implementation of approved plans |
| Senior Code Reviewer 🔍 | `reviewer` | `<MODEL_REVIEWER>` | Independent code verification |
| Project Manager 📋 | `pm` | `<MODEL_PM>` | Process oversight and task lifecycle |

### Updating Models

1. Open your `openclaw.json`
2. Find each agent entry in `agents.list[]`
3. Replace the placeholder with your actual model:
   ```json
   {
     "id": "cto",
     "model": "ollama/qwen3.6:35b",  // was "<MODEL_CTO>"
     ...
   }
   ```
4. Pull models locally before use:
   ```bash
   ollama pull qwen3.6:35b
   ollama pull qwen3.8:27b
   ollama pull laguna-xs-2.1:q4_K_M
   ollama pull ornith-1.5:35b
   ```

---

## 5. DSH Endpoint Configuration

### Production Setup

For production deployments, configure a real DSH API endpoint:

```bash
# In .env or system environment:
DSH_API_BASE=https://dsh-prod.example.com/api
DSH_API_TOKEN=dsh_live_sk_xxxxxxxxxxxxxxxx
```

When `DSH_API_BASE` is set:
- All 10 RuntimeAPI methods attempt real DSH API calls
- Session lifecycle (create, compact, close, info) works end-to-end
- Task submission and tool execution route through DSH
- Model catalog queries return live data

### Development / Standalone Setup

For local development without a live DSH endpoint:

```bash
# Leave DSH_API_BASE empty or unset
DSH_API_BASE=
```

When no DSH API is configured:
- `get_session_info()` → returns `None`
- `compact_session()`, `close_session()`, `archive_session()` → clear error messages
- `spawn_session()` → validation errors (no session creation)
- `submit_task()` → graceful error
- `run_tools()` → policy gate still enforced, DSH call fails with error
- `available_models()` → returns empty list `[]`
- `model_info()` → returns placeholder RuntimeModel with zeroed fields

**This is expected behavior.** The adapter infrastructure is production-ready; it just needs an endpoint to activate.

---

## 6. OpenClaw Integration Paths

DS-EO supports two deployment modes:

### Path A: Within an OpenClaw Agent Session (Recommended for subagents)

When DS-EO runs as a subagent within an OpenClaw gateway session, `session_spawn.py` uses the `sessions_spawn` integration to create real agent sessions. This is the preferred path for multi-agent workflows.

**No configuration needed.** The path is auto-detected by checking for OpenClaw CLI availability and active gateway connection.

### Path B: Standalone REST API Mode (Fallback)

When DS-EO runs as a standalone library, `session_spawn.py` falls back to the OpenClaw Gateway REST API (`/tools/invoke` endpoint). This path requires:
- OpenClaw Gateway running locally on default port
- Valid gateway authentication configured

**Configuration:** Set up your OpenClaw credentials in `~/.openclaw/` per OpenClaw documentation.

---

## 7. Security Notes

### DSH API Token
- Treat `DSH_API_TOKEN` as a secret — never commit to version control
- Use `.env` files (added to `.gitignore`) or system environment variables
- Rotate tokens per deployment environment

### Network Exposure
- If `DSH_API_BASE` points to an internal service, ensure firewall rules restrict access
- Never expose DSH endpoints to the public internet without proper auth and rate limiting

### Ollama Security
- Default `OLLAMA_HOST=localhost:11434` binds only to localhost
- For remote Ollama access, use SSH tunnels or TLS termination proxies

---

## 8. Troubleshooting

### "DSH API unavailable (no base_url configured)"
→ Set `DSH_API_BASE` to your DSH endpoint URL in `.env`.

### Model loading failures / compaction timeouts
→ Only load models needed for the current phase. Use `ollama ps` to check loaded models. Never load more than 3 large models simultaneously on resource-constrained hosts.

### Import errors after migration from `ds_eo_openclaw`
→ See `UPGRADE_FROM_OPENCLAW_EDITION.md` in this directory.

---

## Next Steps

After deployment, proceed to:
1. Run the test suite: `python3 -m pytest tests/ -v`
2. Verify agent models load correctly: check gateway logs
3. Configure your task workflows and channel integrations

<!-- project: github.com/Deepsim-AI/DS-EO -->
