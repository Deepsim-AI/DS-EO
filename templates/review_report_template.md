# Review Report — TASK_<YYYYMMDD>_<NNN>

**Task**: TASK_<YYYYMMDD>_<NNN>
**agent_id**: reviewer
**session_id**: <uuid from gateway runtime>
**model**: ollama/<reviewer-model-name>:<tag>
**produced_at**: <ISO-8601 timestamp>
**Reviewer**: [Agent name/model]
**Date**: YYYY-MM-DD  

[Brief overview of what was reviewed and the overall assessment.]

---

## Recommendation

**Recommendation**: APPROVE / APPROVE_WITH_COMMENTS / REQUEST_CHANGES / REJECT

**Basis**: [One-sentence summary of why this recommendation was made, referencing scoring below.]

---

## Scoring Matrix

| Dimension | Weight | Score (1-5) | Evidence / Justification |
|-----------|--------|-------------|--------------------------|
| Specification Compliance | 40% | _/_5 | [Specific evidence] |
| Code Quality | 25% | _/_5 | [Specific evidence] |
| Architecture Adherence | 25% | _/_5 | [Specific evidence] |
| Test Coverage & Regression | 10% | _/_5 | [Specific evidence] |
| **Weighted Overall** | **100%** | **_/5.0** | [Calculation: sum of weight × score] |

### Threshold Check

- APPROVE requires: Overall ≥ 3.5 AND no dimension below 2 → **[PASS / FAIL]**
- This review's overall: _/_5 → Recommendation matches threshold? **[YES / NO]**

---

## Spec Compliance Assessment

| Requirement ID | Description | Implemented? (Y/N) | Evidence / Gap |
|---------------|-------------|---------------------|----------------|
| <req_id> | <description from spec> | Y / N | [What was verified or what's missing] |
| ... | ... | ... | ... |

---

## Regression Analysis

### Tests Run

| Test Name | Status | Notes |
|-----------|--------|-------|
| `<test>` | PASS / FAIL | [Context for any failure] |

### Findings

[Describe any regressions detected, or state "No regressions detected."]

---

## Code Quality Assessment

### Positive Observations

- [What was done well — naming, structure, patterns, documentation]

### Issues Found

| File | Line (if applicable) | Issue | Severity |
|------|---------------------|-------|----------|
| `<file>` | `<line>` | <description> | Low / Medium / High |

### Suggestions for Improvement

1. [Suggestion 1]
2. [Suggestion 2]

---

## Architecture Adherence Check

- **Existing patterns followed**: [Confirm or describe any deviations]
- **Layer separation maintained**: [Development vs. runtime — confirm boundary preserved]
- **Unauthorized changes**: [None / Describe if any found]

---

## Detailed Findings

[Any additional findings, observations, or context not captured above.]
