#!/bin/bash
set -e

# Read task instruction
TASK_INSTR=$(cat /home/deepsim/ds_eo_openclaw/benchmarks/m1_task_instruction.txt)

echo "Dispatching M1 (qwen3.6:27b) via implementer agent..."

# Use sessions_spawn with explicit model override to qwen3.6:27b
openclaw agents agent --agent implementer --model ollama/qwen3.6:27b \
  --input "$TASK_INSTR" \
  --workspace /home/deepsim/ds_eo_openclaw \
  2>&1

echo "M1 dispatch complete."
