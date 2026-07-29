# TASK_DS_EO_011 — Automated Handoff Message Generation

**Title**: Standardize and automate all cross-role handoff messages  
**Role**: CTO (plan), Implementer (execute), Reviewer (verify)  
**Status**: AWAITING CTO_PLAN.md  

## Context

Every time a task moves between roles (CTO→Implementer, Implementer→Reviewer, Reviewer→CTO, CTO→User), someone manually composes the assignment message. We've just seen this produces inconsistency — today's TASK_DS_EO_010 handoff was well-structured, but there is no template enforcing that structure. The existing `DELEGATE` schema in communication_protocol.md only specifies JSON field names, not the human-readable content format.

This task defines standardized message templates for every handoff direction and proposes automation (a script or runtime mechanism) to generate them from artifact data automatically.

## Scope

1. Define the exact text/template format for all 5 handoff directions
2. Create a reusable `generate_handoff_message.sh` script that reads CTO_PLAN.md and produces the correct formatted message
3. Update communication_protocol.md with these templates as mandatory standards
4. Ensure the Implementer's IMPLEMENTATION_REPORT follows a consistent "handoff to Reviewer" format

## Reference Artifacts

- Communication protocol: `docs/development/protocols/communication_protocol.md`
- Existing CTO→Implementer handoff example (TASK_DS_EO_010): `docs/development/reports/TASK_DS_EO_010/CTO_PLAN.md` + the message sent below it
- Current DELEGATE, IMPL_COMPLETE, REVIEW_COMPLETE schemas in communication_protocol.md

## Deliberate Exclusions

- No runtime automation framework (that's future work — this task defines templates and a script)
- No PM phase integration beyond what's needed for the 5 defined handoff directions
