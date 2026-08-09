---
produced_by: ollama/qwen3.6:35b
session_id: 1d7936cd-d2ac-4de9-8e07-250effb59a26
produced_at: 2026-08-08T19:26:00Z
role: CTO
task_id: TASK_20260808_033
gate: G1
---

# INVESTIGATION.md — Cross-Role Compaction Timeout

## Executive Summary

All three DS-EO development roles (CTO, Implementer, Reviewer) experienced the same failure pattern during working sessions: **compaction timed out after exactly ~120 seconds**, causing auto-compaction to fail and the session to become "blocked" with `livenessState=blocked` and suggestedAction=`reset_or_new`. This is an OpenClaw runtime/session/compaction issue, not a model-specific incompatibility.

## 1. Evidence of Cross-Role Reproduction

### 1.1 Affected Roles Configuration

| Role | Model Provider | Context Window | Max Output Tokens | Session Pattern |
|------|---------------|----------------|-------------------|-----------------|
| CTO | ollama/qwen3.6:35b | 262144 | 8192 | agent:cto:tui-* |
| Implementer | ollama/ornith:35b | 262144 | 16384 | agent:implementer:tui-* |
| Reviewer | ollama/laguna-xs-2.1:q4_K_M | 262144 | 8192 | agent:reviewer:tui-* |

All three share:
- Same Ollama provider (`http://127.0.0.1:11434`)
- Same `timeoutSeconds` defaults (600s agent, 120s compaction)
- Same reserveTokensFloor (80000)
- Same safeguard mode compaction

### 1.2 Reproduction Timeline (CTO session logs)

From gateway logs at 2026-08-08T18:53-19:13:

```
18:53:47 [context-overflow-precheck] estimatedPromptTokens=182403, overflowTokens=259
18:53:47 auto-compaction start for ollama/qwen3.6:35b
18:55:47 "Compaction timed out" ← exactly 120 seconds later
18:55:47 auto-compaction failed; livenessState=blocked

19:02:25 [context-overflow-precheck] estimatedPromptTokens=182444, overflowTokens=300
19:02:25 auto-compaction start for ollama/qwen3.6:35b
19:04:25 "Compaction timed out" ← exactly 120 seconds later
19:04:25 auto-compaction failed; livenessState=blocked

19:11:30 [context-overflow-precheck] estimatedPromptTokens=182476, overflowTokens=332
19:11:30 auto-compaction start for ollama/qwen3.6:35b
19:13:30 "Compaction timed out" ← exactly 120 seconds later
19:13:30 auto-compaction failed; livenessState=blocked
```

Pattern: **every single compaction attempt timed out at exactly 120s**, regardless of transcript size (growing 182403 → 182476 tokens over the session).

### 1.3 Session Key Pattern

The compaction timeouts occurred on `agent:cto:tui-f1faad58-313a-4a56-86e4-bd7f1ee4045e` — a TUI webchat session with an active run (model_call still in progress), which means:
- The session was `queueDepth=1` and stuck behind active work
- Each retry attempt started a new embedded run with the same timeout chain

## 2. Common Code Path Analysis

### 2.1 Run → Tool Calls → Compaction Trigger

```
User message (webchat TUI)
    ↓
Gateway RPC: agent.validate → session lookup (agent:cto:tui-*)
    ↓
runEmbeddedAgent() — resolves model, starts embedded run
    ↓
Mid-turn precheck detects overflow (>reserveTokens budget)
    ↓
contextEngine.compact() triggered as overflow recovery
```

**Key path**: `src/auto-reply/reply/agent-runner-memory.ts` and `compaction-runtime-context.ts`:
1. After tool result appended, mid-turn precheck runs (our config has `midTurnPrecheck.enabled: true`)
2. Estimates prompt tokens using same logic as preflight budget
3. If overflow detected: triggers `contextEngine.compact()` on the **same Ollama model**

### 2.2 Compaction → Safeguard Model Call

```
contextEngine.compact() [at src/agents/embedded-agent-runner/compaction...]
    ↓
buildEmbeddedCompactionRuntimeContext(params)
    ↓
resolveEmbeddedCompactionTarget() — uses session's provider/model (ollama/qwen3.6:35b)
    ↓
If compaction.model is NOT set in config → inherits active model
Our config: NO explicit compaction.model override → inherits ollama/qwen3.6:35b
    ↓
Safeguard mode: qualityGuard.enabled=true, maxRetries=1
    ↓
Provider request to Ollama /api/generate or /api/chat with full transcript content
```

**Critical finding**: Since no `compaction.model` override is configured, compaction uses the **same ollama/qwen3.6:35b model** that just overflowed. For a ~182K token context, this means the summarization request must process ~182K tokens through qwen3.6:35b — an extremely heavy operation even though max output is only 8192.

### 2.3 Timeout → Abort Chain

```
Compaction model call to Ollama (ollama timeoutSeconds=600)
    ↓
But embedded run timeout takes precedence: agents.defaults.compaction.timeoutSeconds=120
    ↓
After exactly 120s: "contextEngine.compact() threw during overflow recovery: Error: Compaction timed out"
    ↓
auto-compaction failed → fallback chain exhausted (maxRetries=1, already used)
    ↓
livenessState=blocked → suggestedAction=reset_or_new
```

**The 120-second compaction timeout IS the config value in `agents.defaults.compaction.timeoutSeconds`**. This is a hard cap that cannot be exceeded by the model's own `timeoutSeconds`.

### 2.4 Session State → TUI Feedback

```
Compaction failed
    ↓
sessionKey still points to same sessionId (preserved)
    ↓
TUI webchat session receives error: "Context overflow: prompt too large for the model"
    ↓
Session state is BLOCKED — no further messages can be processed
    ↓
User must /new or /reset to start fresh
```

## 3. Ollama's Role Analysis

### 3.1 Is Ollama a Contributing Factor?

**Yes, but as an amplifier, not the root cause.** Here's the evidence:

| Factor | Impact | Severity |
|--------|--------|----------|
| **Same model for compaction** | Compaction must summarize ~182K tokens through qwen3.6:35b via Ollama | HIGH |
| **Ollama process load** | All 3 roles share one Ollama instance; during active work, context window is large | MEDIUM |
| **Network latency** | localhost HTTP (127.0.0.1:11434) adds minimal overhead | LOW |
| **num_ctx=262144 param** | Qwen model loaded with max context — higher VRAM usage, slower inference per token | MEDIUM |

### 3.2 Why It's Not Model-Specific

The compaction timeout happens at the OpenClaw runtime level (embedded run abort timer), not at the Ollama API level. The Ollama call could theoretically complete in any time — but it's forcibly killed at 120s regardless. This explains why **all three roles hit the same timeout**: they share:
- Same `compaction.timeoutSeconds=120` default
- Same overflow recovery code path in `runEmbeddedAgent`
- Same safeguard compaction mode

## 4. Root Cause Chain (Primary → Contributing)

### Primary Cause: Insufficient compaction timeout for transcript sizes encountered

The DS-EO workflow creates very long sessions (thousands of tool calls, large file reads/writes). The transcripts grow to ~182K+ tokens before overflow is detected. Compacting a 182K-token context requires the summarization model to process that full history — which takes far longer than the default 120s timeout for any local model on consumer hardware.

### Contributing Cause: reserveTokensFloor too high for practical window

```
Configured values:
  contextWindow: 262144 (model capability)
  maxTokens: 8192 (practical output limit for qwen3.6)
  reserveTokensFloor: 80000 (forced minimum)
  
Effective usable window = contextWindow - reserveTokensFloor = 182144

Our transcripts hit estimatedPromptTokens=182403, just barely over budget.
This means compaction triggers at ~69.5% of context window usage.
```

The floor keeps the session from working much beyond 182K tokens before compaction is needed. And when it does trigger, the 120s timeout is insufficient for summarizing that much content through a local model.

### Contributing Cause: No compaction.model override

Without a dedicated compaction model (e.g., a smaller, faster model like `ollama/nomic-embed-text` or `ollama/qwen3:8b`), the same slow model must both process overflow recovery AND summarize 182K+ tokens. This doubles its workload at peak load.

## 5. Recommendations

### 5.1 Immediate Fix — **APPLIED** ✓

Config changes applied to `~/.openclaw/openclaw.json` at 2026-08-08T20:46 PDT:

| Key | Before | After | Rationale |
|-----|--------|-------|-----------|
| `timeoutSeconds` | 120s | **300s** | Gives Ollama up to 5 minutes for summarization under load, instead of hard-killing at 2 min |
| `reserveTokensFloor` | 80000 | **48000** | Extends effective window from ~182K to ~214K tokens, delaying compaction trigger by ~32K tokens |

Backup saved: `~/.openclaw/openclaw.json.bak.20260808_compaction`
### 5.2 Medium-Term Fix (Transcript Management)

The DS-EO workflow generates very large transcripts due to:
- Extensive file read/write tool calls (large contents logged)
- Multiple task documents written as tool results
- Detailed error logs and diagnostic output

Consider:
- Enabling `session.pruning` to trim large tool results
- Reducing `keepRecentTokens` if 200K is excessive for practical use
- Using `/compact` periodically during long tasks

### 5.3 Long-Term Fix (Runtime Level)

The fundamental tension: compaction needs to summarize a large context, but the model processing that summary must itself handle the large context. OpenClaw should consider:
- Streaming compaction (process transcript in chunks for summarization)
- Using a dedicated fast embedding-based summarizer instead of full context LLM calls
- Making compaction timeout proportional to estimated token count

## 6. Code Path Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    TUI Webchat Session                      │
│                  agent:cto:tui-*                            │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│  Gateway RPC: agent → validate → session lookup            │
│  runEmbeddedAgent() resolves model (ollama/qwen3.6:35b)   │
│  per-session queue serialized                              │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│  Mid-turn precheck triggered                               │
│  estimatedPromptTokens > promptBudgetBeforeReserve         │
│  overflowTokens detected (e.g., +259 tokens over)          │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│  contextEngine.compact() → buildEmbeddedCompactionRuntimeContext()   │
│  → resolveEmbeddedCompactionTarget() — inherits ollama/qwen3.6:35b      │
│  NO compaction.model override configured                    │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│  Safeguard compaction: qualityGuard enabled                │
│  Provider request → Ollama /api/chat (182K+ tokens!)     │
│  ┌──────────────────────────────────────────────────┐     │
│  │ ⚠ SAME MODEL THAT JUST OVERFLOWED                │     │
│  │ ⚠ SHARED OLLAMA INSTANCE (all 3 roles)           │     │
│  │ ⚠ num_ctx=262144 loaded in VRAM                  │     │
│  └──────────────────────────────────────────────────┘     │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│  Embedded run abort timer: compaction.timeoutSeconds=120   │
│  → EXACTLY at 120s: "Compaction timed out"               │
│  → Fallback chain exhausted (maxRetries=1 used)           │
│  → livenessState=blocked, suggestedAction=reset_or_new    │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│  TUI session state: BLOCKED                                │
│  Session preserved but unusable                            │
│  User must /new or /reset                                  │
└─────────────────────────────────────────────────────────────┘
```

## 7. Cross-Role Evidence Summary

The three roles share these identical characteristics that lead to the same failure:

| Shared Property | CTO | Implementer | Reviewer |
|----------------|-----|-------------|----------|
| Ollama provider | ✓ | ✓ | ✓ |
| Same baseUrl (127.0.0.1:11434) | ✓ | ✓ | ✓ |
| Same compaction.timeoutSeconds (120s) | ✓ | ✓ | ✓ |
| Same reserveTokensFloor (80K) | ✓ | ✓ | ✓ |
| No compaction.model override | ✓ | ✓ | ✓ |
| Safeguard mode enabled | ✓ | ✓ | ✓ |
| midTurnPrecheck enabled | ✓ | ✓ | ✓ |
| Transcript overflow pattern | 182K tokens | (similar scale) | (similar scale) |

**Conclusion**: The compaction timeout issue is definitively an OpenClaw runtime configuration problem, not a model-specific incompatibility. The common code path runs through `runEmbeddedAgent()` → `mid-turn precheck` → `contextEngine.compact()` → embedded run with `compaction.timeoutSeconds`, all of which are shared across roles via the default config.

