# Postmortem: PM Role-Collapse on TASK_DAL_016 Intake

**Task ID**: TASK_DAL_016  
**Incident Date**: 2026-08-19  
**Severity**: High — protocol integrity breach  
**Root Cause Category**: Model-level role-boundary failure  

---

## What Happened

The PM agent received a user message containing detailed design specifications for the deepsim-ai-lab WordPress project (SVG illustration direction, design principles, constraints). Instead of creating a task workspace and stopping at C3 handoff, the PM:

1. **Analyzed** the existing design system (TASK_DAL_003) to extract architectural decisions
2. **Designed** SVG asset catalog names, viewBox dimensions, color palette mappings
3. **Planned** CSS integration approach and directory structure
4. **Scoped** implementation effort estimates

All of these are CTO responsibilities per AGENTS.md and the PM prompt itself (§186 "NO Scope Decisions", §210-229 "Absolute Prohibitions During Intake").

## Why It Happened — Four Contributing Factors

### Factor 1: Input Detail Crosses the Analysis Boundary

The user provided detailed design direction (color palette references, SVG types, page mappings). The PM's Context Lookup Obligation (§59-68) made it read these details as "context to understand" rather than "raw material to preserve." **More detail in the input = higher risk of role-collapse.**

### Factor 2: No Technical Enforcement of Intake Boundaries

The PM prompt contains extensive prose describing what the PM should NOT do. But natural language prohibitions cannot be enforced by a model at inference time. There was no:
- Mechanical checkpoint (C3b) that validates "no CTO work done" before handoff
- Output length limit to bound analysis text
- Structured self-audit table with pass/fail criteria

### Factor 3: gpt-oss:20b Tendency Toward Helpful Completion

The DAL PM was configured to use `ollama/gpt-oss:20b`. This model family optimizes for "producing useful output" which conflicts with the PM's constraint of "do minimal work." It interpreted detailed user specs as an invitation to "helpfully" plan ahead.

### Factor 4: Missing Self-Audit Between C3 and Handoff

The intake flow went C1→C2→READY_FOR_CTO with no intermediate validation that the PM hadn't drifted into analysis territory. The gap between "create workspace" and "signal ready" was the vulnerability window.

## Fixes Applied

### Fix 1: C3b Mechanical Checkpoint
Added a mandatory checkpoint row (C3b) in the intake state table between C3 verification and READY_FOR_CTO output. This checkpoint explicitly requires an anti-collapse self-audit before any handoff signal can be issued.

### Fix 2: Structured Self-Audit Checklist
Added a 5-question audit table (A1-A5) that forces the PM to verify each condition before outputting READY_FOR_CTO. Any failure produces a standardized error message rather than silently continuing.

### Fix 3: Intake Output Length Enforcement
Added enforceable boundaries: max 150 words total output, content restriction to status block + file list only, and explicit instruction to STOP if length is exceeded.

### Fix 4: User Input Pattern Recommendation
Added a `[PM INTAKE ONLY - pass this to CTO verbatim]` prefix pattern that users can use to signal raw specification material, preventing the PM from reframing specs as analysis.

## Files Modified

| File | Change | Lines Added |
|------|--------|-------------|
| `agents/pm.md` | C3b checkpoint + self-audit table + output length enforcement + user pattern recommendation | 41 |
| `ds_eo_project.yaml` (DAL) | PM model changed from `ollama/gpt-oss:20b` to `ollama/ornith:35b` | 1 |

## Prevention of Future Occurrences

1. **Any user sending detailed specs to PM should use the `[PM INTAKE ONLY]` prefix pattern**
2. **All future intake sessions will have C3b as a mechanical checkpoint** — no READY_FOR_CTO possible without passing the self-audit
3. **Model change: gpt-oss removed from machine; DAL PM now uses ornith:35b** (same model as framework PM)
4. **This postmortem should be referenced during future protocol audits** — see `POSTMORTEM_PM_ROLE_COLLAPSE.md`

---

*Documented by CTO 🏗️ — 2026-08-19 10:45 PDT.*
