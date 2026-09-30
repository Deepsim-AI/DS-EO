# DS-EO Review Protocol (Global Standard)

**Version**: 1.0  
**Status**: Active  
**Scope**: All OpenClaw workspaces using DS-EO  

---

## Purpose

Defines the review criteria framework, scoring rubric, and required artifacts for the Development Reviewer's independent verification. Ensures reviews are consistent, actionable, and comparable across tasks.

---

## Review Criteria Framework

The Development Reviewer evaluates implementation against four dimensions:

### 1. Specification Compliance (weight: 40%)

Does the implementation satisfy all requirements in the referenced specification?

- [ ] All functional requirements implemented
- [ ] All non-functional requirements addressed (performance, security, etc.)
- [ ] Edge cases from spec are handled
- [ ] No features added that were not in the spec

### 2. Code Quality (weight: 25%)

Is the code well-written and maintainable?

- [ ] Naming conventions followed
- [ ] Code structure is logical and consistent with project patterns
- [ ] Comments/documentation present where needed
- [ ] No unnecessary complexity or dead code
- [ ] Error handling is appropriate

### 3. Architecture Adherence (weight: 25%)

Does the implementation respect the existing architecture?

- [ ] Follows established architectural patterns
- [ ] Does not introduce unauthorized refactoring
- [ ] Maintains separation of concerns (development vs. runtime layers preserved)
- [ ] No cross-layer contamination
- [ ] Backward compatibility maintained for existing interfaces

### 4. Test Coverage & Regression (weight: 10%)

Are tests adequate and are there regressions?

- [ ] New functionality has test coverage
- [ ] Existing tests still pass (no regressions)
- [ ] Edge cases have tests where appropriate
- [ ] No skipped or disabled tests for existing functionality

---

## Scoring Rubric

Each dimension is scored on a 1–5 scale:

| Score | Meaning | Description |
|-------|---------|-------------|
| 5 | Excellent | Fully meets criteria; exceeds expectations in some areas |
| 4 | Good | Meets all criteria with minor improvements possible |
| 3 | Acceptable | Meets core requirements but has notable gaps |
| 2 | Below Standard | Significant issues that need addressing |
| 1 | Unacceptable | Fundamentally flawed; must be substantially redone |

### Composite Scoring

- **Overall Score** = weighted average of the four dimensions
- **Minimum threshold for APPROVE**: Overall ≥ 3.5 AND no individual dimension below 2
- **APPROVE_WITH_COMMENTS**: Overall ≥ 3.0 but < 3.5, or one dimension at 2
- **REQUEST_CHANGES**: Overall < 3.0 OR any dimension below 2

---

## Recommendation Categories

### APPROVE
- All acceptance criteria met
- No regressions detected
- Code quality and architecture adherence acceptable
- Spec compliance confirmed across all requirements

**Use when**: Implementation is complete, correct, and ready to ship.

### APPROVE_WITH_COMMENTS
- Core functionality works correctly
- Minor issues exist (naming, comments, edge cases) that don't block release
- Overall quality is good but not excellent

**Use when**: The work is functionally correct but could be improved. Note comments for future iteration — do not block approval.

### REQUEST_CHANGES
- Significant gaps in spec compliance
- Code quality issues that affect maintainability
- Minor regressions or architecture deviations
- Test coverage insufficient

**Use when**: The implementation needs substantive improvements before it can be approved. Provide specific, actionable feedback.

### REJECT
- Fundamental design flaws
- Major regressions
- Complete non-compliance with spec
- Unauthorized architectural changes

**Use when**: The implementation is fundamentally broken and cannot be fixed through minor changes — the Implementer should revisit from scratch or substantially rework.

---

## Required Review Artifacts

The Development Reviewer must produce:

### 1. Spec Compliance Matrix

| Requirement ID | Requirement Description | Implemented? (Y/N) | Notes |
|---------------|------------------------|---------------------|-------|
| <req_id> | <description> | Y / N | <evidence or gap> |

### 2. Regression Analysis

- List of existing tests run
- Results: pass/fail for each
- Any failures with explanation (new test added? environment issue? genuine regression?)

### 3. Code Quality Assessment

- Key improvements observed (positive feedback)
- Issues found (negative feedback with file/line references)
- Suggestions for improvement

### 4. Architecture Adherence Check

- Confirmation that existing patterns were followed
- Any deviations noted and whether they were authorized
- Layer separation maintained (development vs. runtime agents documented correctly)

---

## Review Process

1. **Preparation**: Read the CTO_PLAN.md, then read the relevant spec. Understand what was supposed to be built.
2. **Diff Analysis**: Run `git diff` and compare against the spec requirements line by line.
3. **Test Execution**: Run all existing tests. Note any failures with context.
4. **Code Inspection**: Review changed files for quality, naming, structure, and architecture adherence.
5. **Scoring**: Apply the scoring rubric to each dimension.
6. **Recommendation**: Issue a recommendation based on composite score and individual dimension scores.
7. **Report**: Produce findings as a session/chat artifact (Reviewer cannot write repository files).

---

## Rules

1. Reviews must be independent — never validate your own work.
2. Every spec requirement must be checked, even if it appears trivially met.
3. Scoring must be justified with evidence from the code or tests.
4. Recommendations must follow the rubric thresholds — not gut feeling.
5. The Reviewer produces findings as a chat artifact; CTO copies into `REVIEW_REPORT.md`.

---

## Related Protocols

- `communication_protocol.md` — Message format standards (REVIEW_COMPLETE)
- `completion_protocol.md` — Reviewer completion checklist
- `handoff_protocol.md` — Phase 3 → 4 transition requirements
