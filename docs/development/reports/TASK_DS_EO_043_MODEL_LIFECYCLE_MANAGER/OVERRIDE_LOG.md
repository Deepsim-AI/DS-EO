# Strategy Override Log — Execution Strategy Manager

**Template format.** This file is populated by `ExecutionStrategySelector` when a user manually overrides the auto-selected strategy.

## Format

```yaml
timestamp: 2026-XX-XXTHX:XM:XSZ
task_id: TASK_DS_EO_XXX
previous_strategy: concurrent|sequential|shared_model
new_strategy: concurrent|sequential|shared_model
source: user_override
reason: "<optional human-provided reason>"
auto_recommended: <strategy auto-detection would have chosen>
---
```

## Example

```yaml
timestamp: "2026-08-14T13:05:00+00:00"
task_id: TASK_DS_EO_043
previous_strategy: sequential
new_strategy: concurrent
source: user_override
reason: "Testing concurrent mode on upgraded hardware"
auto_recommended: sequential
```

## Override History

| Timestamp | Previous | New | Source | Reason | Auto-Recommended |
|-----------|----------|-----|--------|--------|-----------------|
_(Runtime entries appended here)_ |
