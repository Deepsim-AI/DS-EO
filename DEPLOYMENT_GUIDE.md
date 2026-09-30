# DS-EO DSH Edition — Deployment Guide

**Package:** `ds_eo_dsh`  
**Version:** 0.1.0-pre  
**Runtime Requirements:** Python 3.10+, live DeepSeek Harness (DSH) API endpoint  

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│              DS-EO DSH Edition               │
│                                             │
│  ┌───────────┐    ┌──────────────────────┐  │
│  │ RuntimeAPI │◄──►│ DshRuntimeAdapter    │  │
│  │ Protocol   │    │ (HTTP client to DSH) │  │
│  └───────────┘    └──────────────────────┘  │
│           ▲                    │             │
│           │                    ▼             │
│  ┌──────────────┐    ┌──────────────────┐   │
│  │ session_spawn│    │ ModelRegistry     │   │
│  │ (OpenClaw /  │    │ + SHA256 checksum │   │
│  │  DSH REST)   │    └──────────────────┘   │
│  └──────────────┘                            │
└─────────────────┬───────────────────────────┘
                  │ HTTPS
                  ▼
          ┌───────────────┐
          │  DSH API      │
          │ (your host)   │
          │ port/endpoint │
          └───────────────┘
```

DS-EO DSH is a **standalone Python runtime**. It connects to any DeepSeek Harness-compatible backend over HTTP(S). OpenClaw is entirely optional — it's just one way to get agent session management for free.

---

## 1. Deployment Options

### Option A: Production (DSH Backend Configured) ✅

You have a live DSH API endpoint. Set the environment variables and run:

```bash
export DSH_API_BASE="http://your-dsh-host/api"
export DSH_API_TOKEN="your-token"
cd /home/deepsim/ds_eo_dsh
python3 -m ds_eo_dsh.dispatcher.dispatch
```

All 10 RuntimeAPI methods will work end-to-end against your backend.

### Option B: Development (No DSH Backend) ✅

You don't have a DSH endpoint yet. Leave it unset — the code runs in simulation mode:

```bash
unset DSH_API_BASE
cd /home/deepsim/ds_eo_dsh
python3 -m ds_eo_dsh.dispatcher.dispatch
```

Methods return graceful errors instead of crashing. Perfect for testing the orchestration layer, adapter wiring, and session lifecycle logic without a live backend.

### Option C: Production + OpenClaw Integration ✅

You have both a DSH endpoint AND want to run agent sessions inside OpenClaw:

```bash
export DSH_API_BASE="http://your-dsh-host/api"
export DSH_API_TOKEN="your-token"
openclaw gateway start
cd /home/deepsim/ds_eo_dsh
python3 -m ds_eo_dsh.dispatcher.dispatch
```

The dispatcher auto-detects OpenClaw availability and uses it for agent session management (Path A). If OpenClaw isn't available, it falls back to DSH REST directly (Path B).

---

## 2. Environment Variables

### Required for Production

| Variable | Description | Example |
|----------|-------------|---------|
| `DSH_API_BASE` | Your DeepSeek Harness API base URL | `http://localhost:3080/api` |
| `DSH_API_TOKEN` | Bearer token for DSH auth | (your token) |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_HOST` | Fallback model server URL | `localhost:11434` |
| `WORKSPACE_ROOT` | DS-EO data directory | Auto-detected |
| `LOG_LEVEL` | Python logging level | `INFO` |

### Quick Set

```bash
# Production
export DSH_API_BASE="http://your-host/api"
export DSH_API_TOKEN="your-token"

# Development (no DSH)
unset DSH_API_BASE  # All methods return graceful errors

# With OpenClaw (optional)
openclaw gateway start
```

---

## 3. Runtime API Methods (10 Total)

All implemented in `ds_eo_dsh/adapter/dsh_adapter.py`:

| Method | HTTP Verb / Path | Description |
|--------|-----------------|-------------|
| `compact_session()` | `POST /sessions/{key}/compact` | Trigger LLM context compaction |
| `archive_session()` | `POST /sessions/{key}/archive` | Archive a session to cold storage |
| `close_session()` | `POST /sessions/{key}/close` | Mark session closed |
| `get_session_info()` | `GET /sessions/{key}` | Get session metadata (status, turns, context size) |
| `spawn_session()` | `POST /sessions/spawn` | Create a new agent session |
| `submit_task()` | `POST /tasks` | Submit a task for execution |
| `run_tools()` | `POST /tools/{session_key}/invoke` | Execute tool calls within a session |
| `model_info()` | `GET /models/{id}` | Get model metadata (context window, etc.) |
| `available_models()` | `GET /models` | List all available models |
| `run_task()` | `POST /hooks/{tool_name}` | Run a single hook/tool with args |

**When `DSH_API_BASE` is unset:** Each method returns a clear error or placeholder instead of crashing. The adapter layer works correctly; the backend just isn't there.

---

## 4. Testing

```bash
cd /home/deepsim/ds_eo_dsh

# Verify package imports
python3 -c "from ds_eo_dsh import __version__; print(__version__)"

# Run all adapter tests (25/25 pass)
python3 -m pytest tests/test_adapter/ -v

# Verify factory wiring
python3 -c "
import os; os.environ['DSH_API_BASE'] = 'http://localhost:3080'
from ds_eo_dsh import RuntimeAdapterFactory
api = RuntimeAdapterFactory.create(runtime='dsh')
print(f'{type(api).__name__} created OK')
"
```

---

## 5. Model Configuration (Optional — OpenClaw Only)

If you're running DS-EO agents inside OpenClaw, configure the four agent models in `openclaw.json`:

| Agent | ID | Example Model |
|-------|----|---------------|
| CTO / Architect | `cto` | `ollama/qwen3.6:35b` |
| Code Implementer | `implementer` | `ollama/qwen3.8:27b` |
| Senior Reviewer | `reviewer` | `ollama/laguna-xs-2.1:q4_K_M` |
| Project Manager | `pm` | `ollama/ornith-1.5:35b` |

These are the agent models for **build-time engineering**, not the runtime DSH model catalog. They're only relevant if you run DS-EO agents inside OpenClaw. The DSH backend manages its own model routing independently.

---

## 6. Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `"DSH API unavailable (no base_url configured)"` | `DSH_API_BASE` unset | Set it or run in dev mode intentionally |
| `"HTTP 401 Unauthorized"` | Wrong `DSH_API_TOKEN` | Verify your DSH auth token |
| `"HTTP 405 Method Not Allowed"` | Endpoint doesn't support that method | Check your DSH backend version/API spec |
| Import fails | `ds_eo_dsh/VERSION` file missing | It's committed to the repo — if deleted, recreate with `echo "0.1.0-pre" > ds_eo_dsh/VERSION` |

---

<!-- project: github.com/Deepsim-AI/DS-EO -->
