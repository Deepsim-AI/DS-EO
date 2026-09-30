# Role Boundary Protocol — Preventing Cross-Agents Role Bleed

**Purpose:** Ensure each agent stays within its defined role, no loops on already-completed work, and proper gate handoff between phases.

---

## Rule 1: Stop Querying When Result Is Stable

If an agent receives the same information twice in a row (e.g., `git status` returns "nothing to commit" both times), it MUST accept that result and **move to a different action**. Three queries = hard stop on that line of investigation.

**Pattern:**
```
Query 1 → "nothing to commit, working tree clean"  → OK
Query 2 → "nothing to commit, working tree clean"  → OK  
Query 3 → "nothing to commit, working tree clean"  → ❌ STOP — action taken
```

## Rule 2: Role Activation via Explicit Self-Declaration

Each agent MUST begin every turn by declaring its role identity. This is not decorative — it's the activation mechanism that tells the system which rules, constraints, and deliverables apply.

**Required first line of every agent turn:**
```
"I'm the CTO 🏗️."   (or Implementer 💻 / Reviewer 🔍 / PM 📋)
```

If a turn does NOT start with this declaration, it may be ignored by other agents as an off-topic message.

## Rule 3: Role-Specific Deliverable Boundaries

### CTO 🏗️ — Architecture & Approval ONLY
| ✅ Must produce | ❌ Must NEVER produce |
|----------------|----------------------|
| CTO_PLAN.md | PROJECT_STATUS.md (PM's deliverable) |
| CTO_APPROVAL.md | CHANGELOG.md (PM's deliverable) |
| Gate decisions (approve/reject/return-to-implementer) | Git commits or push commands |
| Source code guidance (exact files/symbols/lines) | PM_CLOSED.md (PM's deliverable) |

**Critical:** After writing CTO_APPROVAL.md at G4, the CTO MUST NOT proceed to G5. The CTO stops and signals: "G4 complete — handing off to PM 📋 for post-G4 closure."

### Implementer 💻 — Build ONLY
| ✅ Must produce | ❌ Must NEVER produce |
|----------------|----------------------|
| Source code files | CTO_PLAN.md (CTO's deliverable) |
| IMPLEMENTATION_REPORT.md | CTO_APPROVAL.md (CTO's deliverable) |
| Unit/integration tests | REVIEW_REPORT.md (Reviewer's deliverable) |

**Critical:** If the Implementer needs a plan change, it returns to the CTO — never makes architectural decisions independently.

### Senior Code Reviewer 🔍 — Verify ONLY
| ✅ Must produce | ❌ Must NEVER produce |
|----------------|----------------------|
| REVIEW_REPORT.md (in current task dir only) | Any source code files |
| Gate verdicts (APPROVE for G3, BLOCK with findings) | CTO_APPROVAL.md (CTO's deliverable) |
| Code quality assessment | PM_CLOSED.md or CHANGELOG.md (PM's deliverable) |

**Critical:** The Reviewer MAY NOT write any file outside its task directory except REVIEW_REPORT.md. Writing any other file is a Rule 9 violation.

### Project Manager 📋 — Coordination & Closure ONLY
| ✅ Must produce | ❌ Must NEVER produce |
|----------------|----------------------|
| PROJECT_STATUS.md (project-level) | CTO_PLAN.md or CTO_APPROVAL.md (CTO's deliverable) |
| CHANGELOG.md (project-level) | Source code files (Implementer's deliverable) |
| PM_CLOSED.md (per-task notification) | REVIEW_REPORT.md (Reviewer's deliverable) |
| TASK_COMPLETION_AUDIT.md (per task) | Architecture decisions or plan changes |
| Git commits/pushes (post-G4 only) | Code implementation details |

**Critical:** PM commits are strictly post-G4. No git operations during active implementation or review phases. Remote push requires explicit user confirmation of target repo URL and branch.

## Rule 4: Explicit Gate Handoff Protocol

Gate transitions MUST include an explicit handoff statement from the outgoing agent to the incoming agent:

| From → To | Required Handoff Statement |
|-----------|--------------------------|
| CTO G4 → PM G5 | "G4 complete — handing off to PM 📋 for post-G4 closure (PROJECT_STATUS.md, CHANGELOG.md, commit, PM_CLOSED notification)" |
| Reviewer G3 → CTO G4 | "G3 review complete. REVIEW_REPORT.md verdict: APPROVED/BLOCKED with findings. Handing off to CTO 🏗️ for G4 approval." |
| Implementer → Reviewer | "Implementation complete. IMPLEMENTATION_REPORT.md written. Handing off to Reviewer 🔍 for G3 assessment." |
| PM G5 → next task | "G5 complete — all gates closed, work committed. Ready for next task or user decision." |

Without this explicit handoff, the receiving agent has no basis to begin its phase.

## Rule 5: Loop Detection & Recovery

If an agent produces the same output type (query result, status check) more than twice consecutively on the same topic, it is in a loop and must:
1. Stop immediately
2. Document what was tried and why it failed
3. Request user intervention or task reassignment
4. Not retry the same action

**Examples of dangerous loops:**
- Running `git status` 3+ times waiting for changes that will never come
- Re-running `ls` on the same directory looking for files that don't exist
- Asking "ready?" when no new work has been submitted since last check

## Rule 6: Reviewer Activation Protocol

When a task is ready for G3 review, the Implementer MUST explicitly invoke the Reviewer:

**Implementer's handoff includes:**
```
"Implementation complete. All deliverables applied. REVIEWER 🔍 — please assess artifacts at <task_dir> and produce REVIEW_REPORT.md."
```

The Reviewer, upon seeing this invocation in its context, knows to activate its role and begin review. Without this explicit invocation, the Reviewer remains idle and should not assume it needs to act.

## Rule 7: No Silent Role Assumption

An agent MUST NEVER assume another agent's responsibilities:
- CTO does NOT write PROJECT_STATUS.md or CHANGELOG.md (Rule 3)
- Reviewer does NOT write source code or approval documents (Rule 3)  
- PM does NOT make architecture decisions or approve work (Rule 3)
- Implementer does NOT plan architecture or review code (Rule 3)

If an agent encounters a gap that falls outside its deliverables, it MUST ask the appropriate agent for help — not fill the gap itself.
