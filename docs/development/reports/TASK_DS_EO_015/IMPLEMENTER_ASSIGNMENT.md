**DELEGATE** — Task: TASK_DS_EO_015+017

**Title**: Protocol & Governance Consistency Migration

**Spec Reference**: `docs/development/reports/TASK_DS_EO_015/CTO_PLAN.md`

---

## Implementation Instructions

You are implementing a protocol and governance consistency migration. This involves:
- Editing 9 existing protocol files in `protocols/`
- Creating 1 new file (`GATE_AUTHORITY_MATRIX.md`)
- Updating 2 agent role definitions (`agents/reviewer.md`, `agents/cto.md`)
- Updating PM role definition (`agents/pm.md`)
- Updating `openclaw.json` config (Reviewer tool policy)
- Updating `AGENTS.md` (workspace governance)

**Scope constraint**: Only the files and changes listed in Section 6 of the CTO plan. Do not modify any other files.

---

## Acceptance Criteria

1. All four gate definitions (G1–G4) are consistent across protocols — no divergent criteria
2. No protocol references `PM_STALLED`; all instances renamed to `TASK_STALLED`
3. `delegation_protocol.md` §Step 1 correctly assigns task creation to CTO with PM as requestor only
4. A single G2 Gate Checklist exists in `approval_protocol.md` and is referenced by completion_protocol.md and handoff_protocol.md
5. Each agent's role definition matches its actual write capability:
   - Reviewer can produce REVIEW_REPORT.md (has write + behavioral rule)
   - CTO deny list unchanged for source code (`write, edit, apply_patch` denied)
   - Implementer has full FS access (unchanged)
   - PM writes to designated paths only (unchanged from TASK_DS_EO_014)
6. No agent is assigned a responsibility its tool policy prevents
7. `protocols/GATE_AUTHORITY_MATRIX.md` exists as single source of truth for gate ownership, required artifacts, approval authority, and transition conditions
8. Artifact metadata verification enforced at G3 (handoff prerequisites) and G4 (CTO checklist)
9. Post-rejection artifact handling documented in `approval_protocol.md`
10. Spec lifecycle process defined in `delegation_protocol.md`
11. No agent role definition was modified by a non-owner
12. Protocol files consistent with AGENTS.md §3 ownership model
13. Config changes match protocol changes — exactly one Reviewer tool policy addition (`write` to allow)

---

## Artifact Ownership Summary (Your Deliverable Boundaries)

| Artifact | Your Responsibility | Boundary |
|----------|-------------------|----------|
| `protocols/approval_protocol.md` | Add G2 Gate Checklist section; add metadata enforcement to G4; add auto-reject rule | Edit existing file, add new sections |
| `protocols/communication_protocol.md` | Rename PM_STALLED → TASK_STALLED | Pure rename only |
| `protocols/completion_protocol.md` | Update Implementer pre-G2 checklist reference; update Reviewer checklist + metadata; update PM post-G4 for REVIEW_REPORT.md | Edit existing sections |
| `protocols/delegation_protocol.md` §Step 1 | Replace PM creation actions with CTO ownership; add Spec Lifecycle section | Edit §Step 1 and add new subsection |
| `protocols/handoff_protocol.md` Transition 0 | Clarify PM triggers skeleton, CTO creates it | Edit Transition 0 |
| `protocols/handoff_protocol.md` Transition 0a | Rename TASK_OPEN → TASK_STALLED | Pure rename |
| `protocols/handoff_protocol.md` Transition 2 | Replace prerequisites with reference to G2 Gate Checklist | Edit section header + body |
| `protocols/handoff_protocol.md` Transition 3 | Update handoff method — Reviewer writes directly, CTO no longer copies | Edit Transition 3 |
| **NEW** `protocols/GATE_AUTHORITY_MATRIX.md` | Create with full gate authority table, artifact ownership table, and unified G2 checklist | New file (full content provided in CTO_PLAN.md Section 5) |
| `agents/reviewer.md` | Update: "produce REVIEW_REPORT.md yourself"; add write capability note; add behavioral rule | Edit role definition + tool policy docs |
| `agents/cto.md` | Remove "copies reviewer report" from deliverables; add G4 compliance step | Edit specific sections only |
| `agents/pm.md` | Verify TASK_OPEN sender is CTO (not PM); update delegation reference if needed | Light verification edit if any PM task-creation references remain |
| `openclaw.json` | Add `write` to Reviewer's tools.allow | One-line JSON addition |
| `AGENTS.md` §3 + §5 | Update Reviewer tool policy description; update REVIEW_REPORT.md annotation | Two small edits |

---

## Implementation Order

1. **Config first**: OpenClaw config change — add write to Reviewer allow list
2. **Role definitions second**: reviewer.md, cto.md, pm.md
3. **Protocol files third** (9 files): approval_protocol.md → communication_protocol.md → completion_protocol.md → delegation_protocol.md → handoff_protocol.md (3 transitions) + NEW GATE_AUTHORITY_MATRIX.md
4. **AGENTS.md fifth**: Update ownership references

---

## Delegation Constraints

- Do not modify any file outside the list above
- Follow the CTO_PLAN.md sections precisely — do not add features or scope beyond what's documented
- Produce IMPLEMENTATION_REPORT.md with: files modified, changes made, acceptance criteria verification results
