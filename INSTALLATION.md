# DS-EO DSH Edition — Installation Guide

**Package:** `ds_eo_dsh` (DeepSeek Harness Edition)  
**Version:** 0.1.0-pre  
**Repository:** /home/deepsim/ds_eo_dsh  

---

## What is DS-EO DSH?

DS-EO DSH (Deepsim Engineering Organization — DeepSeek Harness Edition) is the **standalone runtime product**. It implements the `RuntimeAPI` protocol and connects to a live DeepSeek Harness (DSH) backend to orchestrate agent sessions, task dispatch, and model routing.

### What it is NOT

- ❌ Not an OpenClaw plugin or extension
- ❌ Not something you "install into" OpenClaw
- ✅ A Python package (`ds_eo_dsh`) that runs independently

OpenClaw is one **optional** deployment target — if your runtime agent sessions need to live inside OpenClaw. But the code itself has no dependency on OpenClaw being installed.

---

## 1. Prerequisites (Required)

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | ≥ 3.10 | Standard library only (no pip install needed for core runtime) |
| DSH API Endpoint | Any running instance | Set via `DSH_API_BASE` env var; leave empty for dev mode |

## 2. Optional Prerequisites (For OpenClaw Integration)

Only if you want DS-EO to manage agent sessions **through OpenClaw**:

| Requirement | Version | Notes |
|------------|---------|-------|
| OpenClaw Gateway | Latest stable | For OpenClaw session lifecycle support |
| OpenClaw CLI | Installed | For `openclaw gateway start` and subagent spawning |

## 3. Installation (Zero Steps Needed)

The package is **already installed** — it lives in your workspace at `/home/deepsim/ds_eo_dsh/`. No `pip install`, no system-wide setup. Just verify:

```bash
cd /home/deepsim/ds_eo_dsh
python3 -c "from ds_eo_dsh import __version__; print(f'DS-EO DSH Edition v{__version__}')"
# Expected output: DS-EO DSH Edition v0.1.0-pre
```

If it prints the version, you're done.

## 4. Configuration

### Required: Set DSH_API_BASE

To actually use DS-EO (not just run in simulation mode), set your DSH endpoint:

```bash
export DSH_API_BASE="http://your-dsh-endpoint/api"
export DSH_API_TOKEN="your-api-token"
python3 -c "from ds_eo_dsh import RuntimeAdapterFactory; api = RuntimeAdapterFactory.create(runtime='dsh'); print(f'Success: {type(api).__name__}')"
```

### Development Mode (No Endpoint)

If you don't have a DSH endpoint yet, just leave `DSH_API_BASE` unset. All adapter methods return graceful errors instead of crashing — useful for testing the orchestration layer without a backend.

```bash
unset DSH_API_BASE
python3 -c "from ds_eo_dsh import RuntimeAdapterFactory; api = RuntimeAdapterFactory.create(runtime='dsh')"
# Works fine. Methods like available_models() return [] and model_info() returns placeholder data.
```

## 5. Running DS-EO

### Standalone (no OpenClaw)

```bash
cd /home/deepsim/ds_eo_dsh
python3 -m ds_eo_dsh.dispatcher.dispatch
```

This runs the dispatcher with your configured DSH endpoint (or graceful errors if none configured).

### With OpenClaw Integration (optional)

If you also have OpenClaw installed and want multi-agent session support:

```bash
openclaw gateway start  # Start the Gateway
cd /home/deepsim/ds_eo_dsh
python3 -m ds_eo_dsh.dispatcher.dispatch
```

The dispatcher auto-detects whether OpenClaw is available. If it is, it uses OpenClaw for agent session management (Path A). If not, it falls back to the DSH REST API directly (Path B).

## 6. Testing

```bash
cd /home/deepsim/ds_eo_dsh
python3 -m pytest tests/ -v    # Adapter unit tests (25/25 pass)
```

---

## FAQ

**Q: Do I need OpenClaw to use DS-EO DSH?**  
No. OpenClaw is optional. The runtime works entirely independently with just a DSH API endpoint.

**Q: What if I don't have a DSH endpoint yet?**  
Leave `DSH_API_BASE` unset. The adapter returns graceful errors instead of crashing — perfect for development and testing.

**Q: Where does this install to?**  
Nowhere. It's already in your workspace. Just `cd /home/deepsim/ds_eo_dsh && python3 -m ds_eo_dsh.dispatcher.dispatch`.

<!-- project: github.com/Deepsim-AI/DS-EO -->
