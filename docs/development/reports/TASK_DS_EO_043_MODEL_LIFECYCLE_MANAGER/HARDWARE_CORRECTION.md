# Hardware Correction — Jetson AGX Orin 64GB with Integrated GPU

**Date:** 2026-08-14 18:15 PDT  
**Corrected by:** CTO 🏗️  

## Previous Mischaracterization

The IMPLEMENTER_HANG_POSTMORTEM.md incorrectly stated this is a "CPU-only" system. This was wrong.

## Actual Hardware (Verified)

| Component | Value |
|-----------|-------|
| Device | **Jetson AGX Orin Developer Kit** (nvidia,p3737-0000+p3701-0005) |
| SoC | NVIDIA Tegra 234 (Orin) |
| Architecture | aarch64 (ARM64) |
| Total RAM | **64 GB unified memory** |
| GPU | **Integrated NVIDIA GPU** (nvgpu, Orin integrated graphics) |
| Driver | NVIDIA-SMI 540.4.0 / CUDA 12.6 |
| Memory model | **Unified/shared** — GPU and CPU share the same 64GB physical memory |

### How to Verify

- Device tree: `cat /proc/device-tree/compatible` → `nvidia,p3737-0000+p3701-0005 nvidia,tegra234`
- GPU: `/usr/sbin/nvidia-smi` works (though Tegra reports "Not Supported" for dedicated memory because it's unified)
- CUDA packages: `nvidia-cuda-*`, `deepstream-7.1`, `cuda-nsight-compute-12-6` all installed
- Model sizes in use: qwen3.8 17GB + qwen3.6 23GB + laguna-xs 20GB + ornith 21GB + gpt-oss 13GB = **94GB total** (across 5 models, all unified memory)

## Impact on Strategy Decision

The auto-detection in `CapabilityAssessor` needs an update because:

1. **Current code** treats the absence of `nvidia-smi` output as "no GPU" and falls through to the unified path. On Tegra/Orin, `nvidia-smi` *exists* but reports `N/A` for memory because there is no *dedicated* VRAM — it's all shared system RAM.

2. **The decision matrix** should handle Tegra specifically: even with an integrated GPU, the bottleneck is **memory bandwidth**, not VRAM capacity. A single Orin chip has ~100 GB/s memory bandwidth (vs ~700+ GB/s for discrete GPU). Running two 20GB models concurrently will saturate the unified bus regardless of whether both "fit" in 64GB.

3. **Current auto-detection logic**: The `_apply_decision_matrix` method checks `vram is not None and vram > 0` for the discrete GPU path, but on Tegra `detect_gpu_vram()` returns a value (from nvidia-smi memory.total) that may or may not be meaningful for this use case. The memory_type detection already catches "unified" → sequential for <64GB total_mem, which is correct. But on 64GB with an integrated GPU, the bandwidth constraint should drive the decision more aggressively than capacity alone.

## Recommendation for CTO_PLAN.md §4.1 Decision Matrix

Add a Tegra-specific check in `detect_memory_type()`:
- If device-tree contains "tegra" → return "unified_tegra" 
- In the decision matrix, unified_tegra always defaults to **sequential** regardless of total RAM, unless model count = 1

This is not a bug in the current Phase A code — it works correctly for this device because:
- `detect_gpu_vram()` returns None on Tegra (nvidia-smi reports N/A for memory.total)  
- So the discrete GPU path never triggers
- The unified path with total_mem=61.2GB + distinct_models=4 correctly selects sequential

The only improvement would be to make the bandwidth constraint explicit in the reason string rather than relying solely on capacity/ratio thresholds.
