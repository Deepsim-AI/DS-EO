# Auto-Selection Log — Execution Strategy Manager

**Template format.** This file is populated by `CapabilityAssessor` at runtime.

## Format

```yaml
timestamp: 2026-XX-XXTHX:XM:XSZ
task_id: TASK_DS_EO_XXX
hardware_profile:
  total_memory_gb: <float>
  gpu_vram_gb: <float|null>
  memory_type: unified|discrete|unknown
  model_sizes_gb:
    <model_name>: <float>
  active_loaded_models: <int>
  distinct_agent_models: <int>
decision:
  selected_strategy: concurrent|sequential|shared_model
  confidence: <0.0-1.0>
  reason: "<human-readable explanation>"
override: null
---
```

## Auto-detection Signals (6 total)

| Signal | Source | Threshold |
|--------|--------|-----------|
| total_memory_gb | /proc/meminfo or psutil | <32GB → disqualify concurrent |
| gpu_vram_gb | nvidia-smi | 0 → unified path |
| memory_type | Tegra/Apple Silicon check | unified + <64GB → favor sequential |
| model_sizes_gb | ollama list | top-2 sum >60% VRAM/RAM → sequential |
| active_loaded_models | /api/ps | ≥2 large models + new load → sequential |
| distinct_agent_models | agents_list.json | >2 distinct on unified → flag risk |

## Example (on Tegra 64GB)

```yaml
timestamp: "2026-08-14T12:58:00+00:00"
task_id: TASK_DS_EO_043
hardware_profile:
  total_memory_gb: 61.2
  gpu_vram_gb: null
  memory_type: unified
  model_sizes_gb:
    qwen3.6:35b: 23.0
    ornith:35b: 21.0
    laguna-xs-2.1:q4_K_M: 20.0
    gpt-oss:20b: 13.0
  active_loaded_models: 2
  distinct_agent_models: 4
decision:
  selected_strategy: sequential
  confidence: 0.95
  reason: "Unified memory 61.2GB with top-2 models totaling ~44.0GB — sequential required to avoid OOM/bandwidth saturation"
override: null
```
