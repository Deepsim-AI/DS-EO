# DS-EO Runtime Adapter Migration Design

## DeepSeek Harness as the primary runtime; OpenClaw as a legacy compatibility backend

**Scope:** Read-only investigation + design. No product code was modified.

---

## Deliverable A — Current OpenClaw Dependency Map

`OpenClawAPI` lives in `ds_eo/openclaw_api.py` and exposes: `compact_session()`, `archive_session()`, `close_session()`, `get_session_info()` — a thin subprocess wrapper around the OpenClaw CLI. That is the core seam. Additional dependencies:

| # | Dependency | Location | DSH-adjacent (runtime) or config/data? |
|---|---|---|---|
| **A1** | `OpenClawAPI` CLI wrapper (compaction, archive, close, status) | `ds_eo/openclaw_api.py` | **Runtime** |
| **A2** | `subprocess.run(...)` in `release_manager.py:98` | `ds_eo/release_manager.py` | **Runtime** |
| **A3** | Session discovery via `OpenClawAPI` | `ds_eo/session_health/discoverer.py:18` | **Runtime** |
| **A4** | WARN notifications hardcoded `~/.openclaw/notifications/` | `ds_eo/session_health/executor.py:200` | **Config/paths** |
| **A5** | Model registry (cto/implementer/reviewer/pm → `ollama/*`) | `discovery.py`, `execution_strategy`, `workflow_defs` | **Runtime + model registry (A5)** |
| **A6** | `sessions_spawn()` tool-gateway dispatch | `dispatch/dispatch.py` | **Runtime** |
| **A7** | gateway slash-command bindings (`/evo.session`, `/eo.session.list`) | `dispatch/session_dispatch/*.py`, `dispatch/binding_defs/entry_points.yaml` | **OpenClaw-specific glue** |
| **A8** | gateway tool policy (`tool_policy` / `allow`, `deny`) | `dispatcher/session_dispatch/supervisor.py` | **OpenClaw-specific glue** |
| **A9** | `ollama list/show` capability probes | `dispatcher/execution_strategy/capability_assessor.py` | **Runtime (model registry)** |
| **A10** | `~/.openclaw/ds-eo/projects.yaml` + config paths | `project_resolver/*.py` (5 refs) | **Config/data only** |
| **A11** | agent/model constants, tool profile assumptions | `dispatcher/*.md` (AGENTS.md, PROTOCOL.md, ARCHITECTURE.md, SKILL.md, PM_DISPATCHER_SKILL.md), `ds-eo-manifest.yaml` (6 refs) | **Config** |

**Classification:** dependencies **A1–A6, A8–A9** consume the OpenClaw *runtime* API (spawning, compaction, session lifecycle, model routing, tool policy). Dependencies **A7 (bindings), A8 (tool policy), A10, A11** are **OpenClaw-specific configuration/glue**, not runtime — they are the cheapest to migrate and the first candidates to move behind an adapter or a runtime-agnostic config layer. **A6** (`sessions_spawn`) is the single most important: it appears in a dozen files; it is the dispatcher's core "spawn-and-invoke" primitive. The whole point of the migration is to make `ds_eo/` modules free of `session_spawn` coupling — which is a large part of what A6 migration means.

---

## Deliverable B — Proposed Runtime Adapter Architecture

DS-EO currently calls `OpenClawAPI` directly in two places:

- `ds_eo/session_health/discoverer.py:18` uses `from .openclaw_api import OpenClawAPI`
- `ds_eo/session_health/executor.py:23` imports the same

The adapter architecture sits between DS-EO and OpenClaw. DS-EO talks only to `OpenClawAPI` (or one of its runtime adapters); each runtime implements a common `RuntimeAPI`, keeping `ds_eo/` runtime-agnostic.

```
┌──────────────────────────────────────────────────────────────┐
│                    DS-EO (runtime-independent core)            │
│   discovery / dispatch / session_dispatch / reliability     │
└──────────────────────────────┬───────────────────────────────┘
                                │ RuntimeAPI (new abstraction boundary)
     ┌──────────────────────────┴───────────────────────────┐
     │                 ds_eo/adapter (new package)            │
     │   OpenClawRuntimeAdapter · RuntimeSession · ModelInfo  │
     └───────────┬─────────────────────────┬────────────────┘
                 │ implements                │ implements
      ┌───────────▼──────────┐      ┌───────▼──────────────┐
      │  DshRuntimeAdapter   │      │ OpenClawRuntimeAdap.   │
      │  (primary)           │      │  (legacy, read-only)   │
      └───────────┬──────────┘      └───────────┬───────────┘
                  │                          │ (subprocess)
            DeepSeek Harness           OpenClaw API (subprocess)
                  │                          │
            ┌─────▼─────┐              ┌─────▼──────────┐
            │ Ollama     │              │ Ollama         │
            │ (local)    │              │ (local)        │
            └───────────┘              └───────────┘
```

**Why the adapter, not a fork:** DS-EO's discovery/dispatch/reliability logic must stay 100% runtime-agnostic. The adapter package owns the one-time cost of translating the runtime's capabilities (session dispatch, compaction, model registry, tool policy) into a neutral `RuntimeAPI`. That keeps `ds_eo/` modules free of `session_spawn`/`OpenClaw` coupling — the architectural point that makes runtime swaps cheap.

---

## Deliverable C — DSH Integration Design

**Runtime API the adapter presents to DS-EO (one interface, two implementations).** Each method maps one existing OpenClaw use-case to a runtime-agnostic surface:

- `spawn_session()` → the `sessions_spawn()` equivalent (A6).
- `submit_task(task, role, plan) → session` → the `dispatch/dispatch.py:6` equivalent.
- `run_tools(session, tool, args, policy) → tool_result` → the `gateway.tools.allow` policy gate (A8).
- `compact(session)` → compaction; the `OpenClawAPI.compact_session` equivalent (A1).
- `archive(session)` → trajectory bundle (currently `archive_session`).
- `status(session)` → heartbeat / idleness (replaces `discoverer.py`'s OpenClaw discovery, **A3**).
- `register_binding(command, handler)` → slash commands (D2 = "drop OpenClaw slash command bindings; use DSH hooks").
- `model_info(model_id) → RuntimeModel` (context window, gpu_layers, ram, provider).
- `available_models()` → candidate models for A5 selection (`available_models()`, `model_info`).
- `run_task(tool, args) → result` → generic tool execution harness.

**Where each existing OpenClaw dependency lands in DSH (migration mapping):**

| DS-EO dep (A1–A11) | DSH target concept |
|---|---|
| A1 — OpenClawAPI (compaction, archive, close, status) | DSH session lifecycle + DSH compaction hook |
| A2 — release_manager subprocess | DSH `run_task`/hooks |
| A3 — discoverer discovery | DSH session registry + liveness |
| A4 — `~/.openclaw/notifications` | DSH `tool_policy` events / notifications subsystem |
| A5 — model registry (`ollama/*`) | **D1**: model registry now a runtime-agnostic list; resolve to DSH `RuntimeModel` |
| A6 — `sessions_spawn()` | DSH `run_task`/session dispatch |
| A7 — slash bindings | **D2**: DSH hooks replace OpenClaw slash bindings |
| A8 — tool policy | DSH `tool_policy` |
| A9 — ollama capability probes | DSH model routing (`available_models()`, `model_info`) |
| A10 — `~/.openclaw/ds-eo/projects.yaml` | runtime-agnostic config, no CLI dependency (A10 migration) |

**Key:** D1 (model registry) and D2 (slash bindings) are the highest-leverage wins because they are config/glue, not runtime. D1 makes the runtime genuinely pluggable (no `ollama` hardcoding); D2 removes the last OpenClaw-only invocation surface.

---

## Deliverable D — Migration Plan (minimal changes)

**Phase 0 — Foundation (0 risk).** Add the runtime-agnostic adapter package (`ds_eo/adapter/`) exposing the Runtime API above. Read-only; adds nothing. **Phase 1 — DSH adapter, no Go-live.** Implement `DshRuntimeAdapter` against DSH `run_task` + session registry + model routing. All new code, behind an interface. DS-EO still defaults to OpenClaw. **Phase 2 — OpenClaw adapter (thinning).** Move `OpenClawAPI` + `subprocess.run` calls into `OpenClawRuntimeAdapter`, thin and read-only. **Phase 3 — Swap registry.** Point `ds_eo_manifest.yaml` model registry through the adapter (replaces A5). This is the critical path for D1. **Phase 4 — Swap bindings.** Replace A7 slash-command bindings with DSH hooks (D2). This is the critical path for D2. **Phase 5 — Swap discovery.** Point `discoverer.py` at DSH session registry/heartbeat (**A3**) instead of OpenClaw API. **Phase 6 — Smoke tests + Go-live.** Re-run existing tests against DSH adapter; once green, flip the default. **Phase 7 (optional):** migrate the two remaining OpenClaw deps; keep OpenClaw adapter as legacy backend.

The single most important safety rule: **DS-EO core never calls OpenClaw.** The adapter is the only file that touches the runtime. That's the architectural guarantee that makes future runtime swaps cheap.

---

## Deliverable E — Reliability Comparison & Test Methodology

Run `DS-EO + OpenClaw` vs `DS-EO + DSH` on an identical set of representative tasks; instrument with the same harness.

**Metrics (per task, averaged, multiple runs):**
- **Task completion rate** % — does G4/complete finish end-to-end?
- **Tool executions succeeded** % — `run_tools` reliability (D8).
- **Run errors (HTTP 500 count)** — OpenClaw-specific failure class (from inspection).
- **Idleness events** — count of `status()` reporting idle.
- **Avg latency**, **p95 latency** per turn.
- **Recovery success** % — after injected run error, does recovery resume?
- **Context handling** — does context window stay bounded; compaction errors observed?
- **Memory / RAM peak** during long-running execution.
- **Long-running stability** — run 100+ tasks; track drift, session leaks, completion rate over time.

**Method:** same `ds-eo-manifest` configs; same tasks; same failure injections. Report per metric as a comparison matrix. This directly answers the "which does the harness own" question.

---

## Deliverable F — Risks & Limitations

- **Read-only scope:** this is design-investigation only; implementation is separate work.
- **Environment:** read-only session; adapter can't be validated in-place here.
- **Context window as the shared constraint:** DSH is not immune to context errors — compaction still happens under the hood. The DSH adapter is the *better* layer for handling it, but Ollama/GPU/hardware limits at the bottom of the stack remain Ollama's and the hardware's.
- **Ollama is a provider, not the harness:** even on DSH, **A5** model registry lives above the provider; hardware/GPU/Ollama failures are not "DSH bugs," they're the runtime-layer boundary.
- **Tool policy (A8) mapping is non-trivial:** DSH `tool policy` must faithfully replicate OpenClaw `gateway.tools.allow` semantics, or behavior changes.
- **Slash-command semantics (A7/D2):** DSH hooks must preserve existing binding behavior; risk of behavioral drift.
- **Config/data isolation (A4, A10):** `~/.openclaw/notifications` / `projects.yaml` paths must be replaced with runtime-agnostic locations — the two failing WARN tests are proof this migration is real work, not cosmetic.
- **Backwards compatibility:** keeping OpenClaw as a legacy backend increases surface; must not regress the OpenClaw path.

---

## Deliverable G — Recommended Next Implementation Step

**Build Phase 0 + 1 + 2 together:** create the `ds_eo/adapter` package with the Runtime API, then implement `DshRuntimeAdapter` and the thin `OpenClawRuntimeAdapter`. That one change delivers the whole architectural point ("DS-EO depends on the Runtime API, not OpenClaw"), unlocks D1 and D2 cleanly, and gives a runnable baseline to run Deliverable E.

**Do it before:** D1/D2 wiring (model registry, slash bindings).
**Do it after:** Phase 3+ (full OpenClaw removal), Phase 4+ (config isolation), Phase 5 (verification).

---

## Answer to "leave it at this deliverable"

This is a design artifact, not product code. No production changes were made.

**No strong recommendation.** Save the doc — say the path and it becomes an on-disk artifact for this phase; if you've completed review we can close it. If a file is wanted, `/home/deepsim/ds_eo_dsh_test/RUNTIME_ADAPTER_DESIGN.md` is a sensible location.
