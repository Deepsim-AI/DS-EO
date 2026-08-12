# Source Inspection Protocol — Preventing Context-Pressure Failures

## Purpose

Prevents agent sessions from crashing due to context overflow when inspecting source code. Affects all agents but is especially critical for the Implementer (G2 phase) and Reviewer (G3 phase), which must read or write source files.

**Triggered by**: Any task involving reading, editing, or verifying source code in large bundled/generated files (OpenClaw dist bundles, build artifacts, generated output).

**Root cause of TASK_DS_EO_039 failure**: Implementer sessions loaded entire 200KB+ JS bundles into context to verify changes. Each read added ~50-100K tokens to the prompt, pushing compaction past its timeout threshold on CPU-only hardware. Multiple recovery attempts in the same session compounded the problem.

---

## AGENTS.md Governance Rules (Layer 1)

### Rule — Bounded Source Inspection

Every agent MUST follow these bounded-context rules when working with source code:

**R-SI-1: Never read large bundled files wholesale.** Do not load an entire OpenClaw dist bundle or build artifact into context unless no other option exists. Use grep, symbol search, and targeted line reads instead.

**R-SI-2: CTO plans MUST include file/symbol/line-range guidance.** Every task in the CTO plan that touches source code must specify the exact file path, function/symbol name, and approximate line number. This allows all downstream agents to use targeted inspection.

**R-SI-3: Implementer session recovery rule.** If an Implementer session reaches compaction timeout (context overflow): stop immediately, write a `COMPACTION_FAILURE.md` to the task directory documenting exactly where work was lost, and request the user to start a fresh session. Do not attempt repeated compaction within the same session — it compounds the problem.

**R-SI-4: Implementation evidence before reporting.** The Implementer's primary deliverable is working code with inline change markers (e.g., `// TASK_DS_EO_039 Task N:`). A detailed implementation report may be produced by CTO or PM from the git diff, patch files, and completion notes if the Implementer session is already under context pressure. The Implementer MUST provide a concise completion note listing each task status before its session closes.

**R-SI-5: Model replacement is not a first response to run errors.** When encountering repeated run errors (compaction failures, tool timeouts, session crashes), agents and users must diagnose the root cause before considering model replacement:
1. **Context pressure**: Check token usage (`session_status` input tokens vs reserveTokensFloor). If approaching compaction threshold → reduce file reads, use grep instead of full-file reads.
2. **Excessive tool loops**: Check if a single agent is making >50 tool calls per turn → break work into smaller sessions.
3. **Compaction failures**: Check if compaction timeout was exceeded → start fresh session, not retry same one.
4. **Session lifecycle issues**: Check if the session has been idle too long or hit max duration → restart, don't escalate.
5. **Only then consider model limitations**: If none of 1-4 apply and the error persists across multiple fresh sessions with bounded context, investigate model capability limits.

**R-SI-6: Separation of implementation from reporting.** Implementing code and writing detailed documentation are distinct activities that compete for the same token budget. Agents should:
- Use one session focused on code changes (Implementer)
- Use a separate, fresh session focused on review/reporting (Reviewer or PM)
- If a single session must do both, produce completion evidence inline with code changes and defer documentation to a fresh session

---

## Implementer Skill Operating Procedure (Layer 2 — Detailed)

### Before Working on Source Files

1. **Check CTO plan for exact file/symbol/line guidance.** Every task should have this. If it does not, request it from the CTO before proceeding (this is a G1 defect in the plan).
2. **Check current context pressure.** Run `session_status` and check input token count vs reserveTokensFloor. If already above 70% of the window, consider a fresh session.
3. **Back up any file you modify.** Create `.bak_<TASK_ID>` before editing.

### During Source File Work

4. **Never load an entire bundled/generate file into context.** This includes:
   - OpenClaw dist bundles (`get-reply-*.js`, `tui-*.js`, `run-state-*.js`, etc.)
   - Build output directories
   - Generated type definition files (.d.ts)
   - Any single file over 50KB

5. **Use bounded inspection patterns:**
   ```
   # Grep for the function or symbol you need:
   grep -n "functionName\|TASK_DS_EO_XXX" path/to/file.js

   # Read only a focused line range (20-30 lines):
   sed -n '1234,1260p' path/to/file.js

   # Get file size before reading:
   wc -c path/to/file.js    # if >50000 bytes, do NOT read wholesale

   # For patch verification: use diff with known backup:
   diff backup_file current_file | head -100
   ```

6. **Work in bounded phases** (each phase should be completable without compaction):
   - Phase A: Verify existing state (grep → identify line numbers) — 5 tool calls max
   - Phase B: Apply change via targeted write/patch — file-size of change, not total file
   - Phase C: Verify change with targeted grep/sed — 3 tool calls max
   - Each phase boundary = opportunity to check context pressure

7. **Do NOT repeat compaction attempts.** If auto-compaction fails:
   - Write `COMPACTION_FAILURE.md` to the task directory (save all in-progress artifacts there)
   - Stop — do not try again in this session
   - Request user to start a fresh session with the saved context

### Session Health Monitoring

8. **Check context pressure at these checkpoints:**
   - Before starting any phase that requires reading source
   - After each 10 tool calls
   - When a read returns >5KB of output
   - Before beginning documentation/reporting work

9. **Start a fresh session when:**
   - Input tokens exceed 70% of reserveTokensFloor
   - Auto-compaction has failed twice
   - You need to both implement code AND produce documentation
   - A source file you must read is >100KB (delegate verification to CTO with grep-guided inspection)

---

## CTO Skill Operating Procedure (Layer 2 — Guidance)

### During Plan Writing

1. **Provide exact source-file guidance for every task.** Each task in the CTO plan MUST include:
   - File path relative to OpenClaw dist or project root
   - Function/symbol name being modified
   - Approximate line number or offset range
   - Before/after code snippet (≤15 lines)
   - Why this location is correct

2. **Do NOT require the Implementer to read full source files.** The CTO plan should give enough context that the Implementer only needs targeted reads. If the task requires understanding 3+ unrelated functions in a large file, decompose it into smaller tasks.

### During Verification (G4)

3. **Use grep-guided verification, not wholesale reading.** When verifying implementation:
   - Search for `// TASK_DS_EO_XXX Task N:` markers left by the Implementer
   - Read only 10-20 line contexts around each marker using `sed -n 'L,Rp'`
   - Verify logic correctness via targeted read, not by loading the entire file
   - Compare against the CTO plan's before/after snippets

4. **If verification requires >30KB of source reading, request Implementer assistance.** The Implementer may have already inspected the area during coding. Ask them to verify specific points rather than re-reading everything yourself.

---

## Reporting Protocol (Layer 2 — Lightweight)

### Implementer Deliverable (Minimal Viable Evidence)

The Implementer's core deliverable is **working code with inline markers**. A detailed report is secondary:

```
IMPLEMENTATION_STATUS.md (lightweight, ≤200 lines):

TASK_DS_EO_XXX Implementation Status
=====================================

Task 1: [APPLIED | FAILED: <reason>]
- File: get-reply-OTG64ybi.js, line ~3577
- Method: Verified via grep for TASK_DS_EO_039 marker and sed line context read
- Change: [one-line summary]

Task 2: [APPLIED | FAILED: <reason>]
...

[Optional: diff output or patch file reference if >10 changes]
```

The Implementer MUST write this file before closing their session. If they cannot due to compaction, they should write `COMPACTION_FAILURE.md` with the same structure.

### CTO/PM Report Construction (When Implementer Is Under Pressure)

CTO and PM may construct a full IMPLEMENTATION_REPORT.md from:
1. The CTO plan (`CTO_PLAN.md`) — specification layer
2. Git diff (`git diff`) — actual changes
3. Patch files in `patches/TASK_XXX/` — detailed before/after
4. Implementer's completion evidence (`IMPLEMENTATION_STATUS.md` or inline code markers)
5. Test results (if any)

This is explicitly permitted by R-SI-4 and does not violate any gate requirements. The IMPLEMENTATION_REPORT.md requirement exists to document work completed, but the *content* can be synthesized from these sources without requiring the Implementer session to hold all of it in context simultaneously.
