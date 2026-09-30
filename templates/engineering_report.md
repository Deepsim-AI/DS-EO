# Engineering Report — {{DATE}}

**Reporting Period**: {{START_DATE}} → {{END_DATE}}  
**Compiled By**: PM (Project Manager) agent  

---

## Task Completion Rate

<!-- Aggregation across all active tasks. Not per-task detail — that's in implementation reports. -->

| Metric | Value |
|--------|-------|
| **Total Active Tasks** | {{COUNT}} |
| **Completed This Period** | {{COUNT}} |
| **Open (Not Started)** | {{COUNT}} |
| **In Progress / Tracking** | {{COUNT}} |
| **Stalled** | {{COUNT}} |
| **Completion Rate** | {{PERCENTAGE}}% |

---

## Quality Metrics (From Reviewer Reports)

<!-- Aggregate quality signals from individual review reports. Summarize trends, not per-task scores. -->

### Review Outcomes This Period

| Recommendation | Count | Percentage |
|----------------|-------|------------|
| APPROVE | {{COUNT}} | {{PERCENTAGE}}% |
| APPROVE_WITH_COMMENTS | {{COUNT}} | {{PERCENTAGE}}% |
| REQUEST_CHANGES | {{COUNT}} | {{PERCENTAGE}}% |
| REJECT | {{COUNT}} | {{PERCENTAGE}}% |

### Quality Trends

<!-- Note any patterns: recurring issue types, improving/deteriorating scores, systemic concerns. -->

- <!-- Trend observation 1 -->
- ...

---

## Milestone Progress

<!-- High-level view of where the project stands relative to milestones in ROADMAP.md. Not task-by-task — milestone level only. -->

### Current Milestone: {{MILESTONE_NAME}} ({{VERSION}})

| Objective | Status | Notes |
|-----------|--------|-------|
| <!-- Objective from roadmap --> | Achieved / In Progress / Not Started | <!-- Brief note --> |
| ... | ... | ... |

---

## Release Readiness Assessment

<!-- PM-level assessment of whether the current set of completed work constitutes a release-worthy state. Does NOT make technical decisions — reports on what's assembled vs. what's needed. -->

### Artifact Completeness

- [ ] All required task artifacts collected and verified
- [ ] Documentation synchronized with code
- [ ] CHANGELOG entries compiled from individual tasks
- [ ] Milestone tracking updated

### Open Items Before Release

| Item | Source (Task) | Status | Notes |
|------|---------------|--------|-------|
| <!-- What's missing --> | TASK-YYYYMMDD-NNN | ... | ... |
| ... | ... | ... | ... |

---

*Next engineering report scheduled: {{NEXT_REPORT_DATE}}*
