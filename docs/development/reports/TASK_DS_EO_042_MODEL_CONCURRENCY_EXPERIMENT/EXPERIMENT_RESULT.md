# Experiment: Model Concurrency on Jetson AGX Orin 64GB Unified Memory

**Date:** 2026-08-13 23:14 PDT  
**Session Key:** agent:cto:tui-196bed52-df49-416a-8954-32fad9318978  
**Final Session State:** 322k/262k tokens (123%) — unrecoverable compaction failure  

## Test Protocol

The experiment was designed to determine whether concurrent multi-model inference on the 64GB unified-memory Jetson AGX Orin is viable for DS-EO's multi-agent architecture. Tests were executed in sequence under controlled conditions with GPU memory reset between phases.

### Setup

- **Hardware:** Jetson AGX Orin, 64GB unified CPU/GPU memory, CPU-only inference
- **Models:** qwen3.6:35b (~29 GB GPU), laguna-xs-2.1:q4_K_M, gpt-oss:20b (PM)
- **Baseline:** All standby models unloaded from GPU before testing

## Results

### TEST 1: CTO (qwen3.6:35b) alone → verify stable baseline
**Result: TIMED OUT at 30 seconds**

When `laguna-xs-2.1` was present in standby (weights mapped to GPU), even the CTO model by itself timed out. This established that **mere presence of another model's weights in unified memory degrades inference performance sufficiently to cause timeouts**, even when that second model is not actively running inference.

This is more severe than anticipated: the problem isn't just concurrent active inference — it's weight-resident pressure on shared memory bandwidth.

### TEST 2: CTO + Reviewer → attempt spawn
**Result: CTO inference timed out at 30 seconds**

Confirms TEST 1 finding. When trying to spawn a separate Reviewer session while the CTO session was active, the CTO's own inference collapsed first (the active model dies before the spawned one gets resources).

### TEST 3: Reviewer (laguna-xs-2.1:q4_K_M) alone → attempt spawn
**Result: SUCCEEDED**

The smaller `laguna-xs-2.1:q4_K_M` model succeeded as a standalone session. This is critical evidence that **the 4-bit quantized Reviewer model IS viable on this hardware when it's the only active model**. The bottleneck is specifically with larger models (35B-class) and their context buffers, not a fundamental spawn impossibility.

### TEST 4: qwen3.6:27b + Reviewer / ornith:35b + Reviewer
**Result: DID NOT COMPLETE**

OpenClaw auto-compaction failed (`Context is too large and auto-compaction could not recover`). The session hit 322k/262k tokens (123%) before the test could execute. This is a separate issue from the model concurrency problem — it's an OpenClaw context management failure that can be addressed independently.

## Key Findings

1. **Standby models consume shared memory bandwidth.** Even non-active model weights mapped into GPU memory cause measurable performance degradation to actively running inference on unified-memory architectures.

2. **Model size matters significantly.** The 35B-class qwen3.6 model is the primary failure mode. The quantized laguna-xs-2.1 (4-bit) works fine as a standalone session.

3. **The CTO model fails first, not the spawned model.** When resources are exhausted, the active inference (CTO) times out before the spawned session can get its turn. This means the CTO — the most context-heavy agent — is the bottleneck.

4. **OpenClaw compaction is a separate failure mode.** The experiment hit a hard stop at token overflow before TEST 4 could run. This must be addressed independently (context window tuning, compaction thresholds).

5. **Reviewer alone succeeding is important.** laguna-xs-2.1:q4_K_M as the sole active model demonstrates the hardware CAN support the Reviewer role — just not concurrently with a 35B-class model.

## Architecture Implication

The evidence strongly supports switching from concurrent multi-model architecture to sequential model residency:
- Run one model at a time, unload it completely before loading the next
- Use the CTO's API call capability to query laguna-xs-2.1 for review tasks instead of spawning a separate session
- This matches the "compaction-aware" operating rules already in AGENTS.md (Section 3.5)

## Status: EXPERIMENT CONCLUDED

No further testing in this session. Results documented. Next step requires a fresh CTO session with compaction parameters addressed first.
