You are the **Implementer**.


## DISPATCH: G1_APPROVE

Task: `TASK_DAL_002`


## Task Context

- plan_content: # CTO Plan — TASK_DAL_002

**Task ID**: TASK_DAL_002  
**Phase**: 1  
**Title**: Content Inventory + Information Architecture  
**Date**: 2026-08-05  
**Project**: Deepsim AI Lab WordPress Website  
**CTO**: qwen3.6:35b (ollama)

---

## 1. Problem Statement

The product spec (§2, §25) requires a thorough inventory of existing Deepsim content before any website building begins. This task classifies what to keep, update, merge, rewrite, archive, or skip — creating a coherent information architecture (IA) and migration strategy rather than reproducing the old site verbatim.

All 6 reference sources have been successfully fetched and cataloged (see TASK_DAL_001 `inspection_report.md` and this plan's appendix). The content inventory is based on **live data** fetched today (2026-08-05) to capture any updates since the Phase 0 inspection.

## 2. Input Sources (All Fetched Live 2026-08-05)

| # | Source | URL | Content Type | Fetch Status |
|---|--------|-----|-------------|-------------|
| 1 | Labs/Platforms | deepsim.ca/labs/ | Platforms, Python packages, AI models | ✅ HTTP 200 |
| 2 | Research/Areas | deepsim.ca/research/ | 5 research areas, featured projects, highlights | ✅ HTTP 200 |
| 3 | Projects | deepsim.ca/projects/ | 5 detailed project pages | ✅ HTTP 200 |
| 4 | Publications | deepsim.ca/publications/ | 7 journal papers (2021-2025), 13 books (2005-2026) | ✅ HTTP 200 |
| 5 | Contact | deepsim.ca/contact/ | Address, phone, email | ✅ HTTP 200 |
| 6 | GitHub Org | github.com/Deepsim-AI | Org description, repo links | ✅ HTTP 200 |

## 3. Research Taxonomy (Derived from Actual Content)

The taxonomy below is **derived exclusively from deepsim.ca/research/** and verified against deepsim.ca/labs/:

| # | Research Area | Sources Confirming It |
|---|--------------|----------------------|
| 1 | Machine Learning | deepsim.ca/research/; deepsim.ca/labs/ (Forecasting Models, Deep Learning) |
| 2 | Computer Vision | deepsim.ca/research/; deepsim.ca/labs/ (CV Models); Plant Disease Detection project |
| 3 | Data Science | deepsim.ca/research/; extensive Python book series and utilities |
| 4 | IoT & Edge Intelligence | deepsim.ca/research/; USV, Water Monitoring platforms |
| 5 | Signal & Time Series | deepsim.ca/research/; WaveletMind platform, wavelet transform books (6 volumes) |

**Note**: These 5 areas match exactly the taxonomy on the current Deepsim site. Do not invent additional areas. Consider adding "System Dynamic Simulation" and "Reinforcement Learning" as sub-areas of ML if they appear in specific project content.

## 4. Content Inventory & Disposition Classification

### 4.1 Platforms (from deepsim.ca/labs/)

| Platform | Current State | Proposed Disposition | Reason |
|----------|--------------|---------------------|--------|
| Smart Water Quality USV System | Detailed description with tags | **KEEP + UPDATE** | Core featured project; needs IA placement under Projects/Featured |
| Intelligent Water Quality Monitoring | Description present | **KEEP** | Relevant to Research/Water area |
| AI Companion System | Description + book reference | **UPDATE** (cross-link) | Strong content; link from People + Projects sections |
| WaveletMind | Framework description | **MERGE** into Signal & Time Series research area | Overlaps with wavelet books/research |
| Data Analysis App | Platform entry | **KEEP** as tool/utility | Useful for "Tools" subsection |
| Water Quality Early Warning | Description present | **MERGE** into Projects/Water Monitoring | Redundant with USV project description |

### 4.2 Python Packages (from deepsim.ca/labs/)

| Package | Proposed Disposition | Notes |
|---------|---------------------|-------|
| descripstats | KEEP as "Tools" → Developer Utilities | Practical utility |
| normscaler | KEEP as "Tools" → Developer Utilities | ML preprocessing tool |
| sub-superscript-generator | ARCHIVE (low relevance to new site) | Niche LaTeX-style utility |
| image-data-split | KEEP as "Tools" → Developer Utilities | CV workflow tool |
| upload-to-github | ARCHIVE (tool-specific, not product-relevant) | Low strategic value |
| modelselect | KEEP as "Tools" → Developer Utilities | ML workflow tool |

### 4.3 Research Areas (from deepsim.ca/research/)

All 5 areas confirmed and verified: **Machine Learning, Computer Vision, Data Science, IoT & Edge Intelligence, Signal & Time Series**. Use these as the navigation-level research taxonomy. Each area page will feature relevant projects, publications, and team members in its subsection.

### 4.4 Projects (from deepsim.ca/projects/)

| Project | Current URL | Proposed Disposition | Featured? |
|---------|-------------|---------------------|----------|
| Water Monitoring USV | /projects/srwqmew-usv | **KEEP** — detailed methodology and results | ✅ Yes (featured) |
| Real-time Water Environment Monitoring | /projects/water-monitoring | **KEEP + UPDATE** — strong content, needs IA alignment | ✅ Yes (featured) |
| River Health Estimation | /projects/river-health | **KEEP** — international collaboration proof | Yes (secondary) |
| Human Behavior Recognition | /projects/human-behavior | **UPDATE** — publish a link from Research/CV area + Publications | Secondary |
| Plant Disease Detection (TVITA) | /projects/plant-disease | **UPDATE** — link to TVITA publication + CV research area | Secondary |

### 4.5 Publications (from deepsim.ca/publications/)

| Category | Count | Proposed Disposition |
|----------|-------|---------------------|
| Journal Papers (2021-2025) | 7 papers with DOIs | **KEEP** — all DOI-linked; list on Publications page |
| Books (2005-2026) | 13 books, 9 from 2026 via Zenodo DOIs | **KEEP + UPDATE** — organize by series (Wavelet Transform in Practice = 6 vols; Data Science/ML series = multiple vols) |

### 4.6 Contact Information

| Field | Source | Proposed Disposition |
|-------|--------|---------------------|
| Address: 32633 Simon Avenue, BC V2T 0G9, Abbotsford, Canada | deepsim.ca/contact/ | **KEEP** on Contact page |
| Phone: 778-800-0109 | deepsim.ca/contact/ | **KEEP** on Contact page |
| Email: contact@deepsim.ca | deepsim.ca/contact/ | **KEEP** on Contact page |

### 4.7 GitHub Organization (github.com/Deepsim-AI)

| Item | Proposed Disposition |
|------|---------------------|
| Org description + Chief Scientist ORCID: 0000-0002-4665-5366 | **KEEP** — link on About page or People profile |
| Link to shoukewei GitHub | **KEEP** — link on About page, "Open Source" section |

### 4.8 Additional Content Found (Not in original spec §2)

| Source | Proposed Disposition |
|--------|---------------------|
| Deepsim Insights (insights.deepsim.ca, launched May 2026) | **KEEP** — feeds "News/Insights" section |
| Deepsim Press Affiliate Program | **ARCHIVE** (not core to new site; may be a blog post if needed) |
| DS-EO OpenClaw Edition release notes | **MERGE** into News/Insights as a product announcement |

## 5. Information Architecture (IA)

### 5.1 Primary Navigation (per spec §3, validated against actual Deepsim content)

```
Home
├── About
│   └── Team / People
├── Research
│   ├── Machine Learning
│   ├── Computer Vision
│   ├── Data Science
│   ├── IoT & Edge Intelligence
│   └── Signal & Time Series
├── Projects
│   ├── Featured (USV, Water Monitoring)
│   ├── All Projects
│   └── Open Source
├── Publications
│   ├── Journal Papers
│   ├── Books / Deepsim Press
│   └── Research Highlights
├── People
│   ├── Dr. Shouke Wei (Founder & Chief Scientist)
│   └── Team (TBD — pending team content availability)
├── News / Insights
│   └── Blog Archive
└── Contact
```

### 5.2 Page Hierarchy Details

#### Home
- Hero: "Advancing Knowledge. Building Intelligent Systems." (tagline from deepsim.ca/research/)
- Featured projects carousel (USV + Water Monitoring)
- Recent publications ticker
- Quick links to Research areas
- Latest Insights/News

#### About
- Mission & Vision derived from research area descriptions on deepsim.ca/research/
- "Research. Collaborate. Advance Together." positioning from existing content
- **Open Source**: Link to github.com/Deepsim-AI + shoukewei GitHub
- Contact summary (address, phone)

#### Research → [Each Area]
Each of the 5 research areas gets its own page with:
- Description (derived from deepsim.ca/research/)
- Related projects (filtered from project list)
- Related publications (filtered from publication list)
- Potential team members (if identifiable)

#### Projects
- **Featured**: DS-AIOS (USV Water Monitoring), DS-EO (workflow platform) as per spec §3
- **All Projects** grid: 5 projects with cards (title, short description, tags)
- Each project page: full methodology, results, technologies used

#### Publications
- Filterable list: Journal Papers + Books by year/type
- DOI links to Zenodo/journals preserved
- Wavelet Transform in Practice series grouped as a collection (6 volumes)
- Data Science/ML book series grouped separately

#### People
- Dr. Shouke Wei: Founder & Chief Scientist, ORCID 0000-0002-4665-5366, PhD from ... (from book publisher info + contact)
- Team section: **PLACEHOLDER** — insufficient public team data; propose "Our Team" page for future expansion

#### News / Insights
- insights.deepsim.ca RSS or manual feed integration
- DS-EO release notes as product news
- Book launch announcements (Deepsim Press)

#### Contact
- Address, phone, email from deepsim.ca/contact/
- Map embed (Google Maps / OpenStreetMap)
- Social links (GitHub: github.com/Deepsim-AI)

## 6. Implementation Plan

The Implementer shall produce the following artifacts:

### Step 1: Write `docs/IA_document.md`
This document must contain:
- Full IA tree (as sectioned above, with all subpages documented)
- Navigation structure with WordPress menu hierarchy
- Page-to-content mapping table (every page lists what source content it uses)
- Gap analysis for missing content (e.g., team photos, detailed biographies, press releases)

### Step 2: Write `docs/content_migration_matrix.md`
This document must contain a **row-by-row migration table** with columns:
| Source Content | Target Page/Section | Disposition | Priority | Notes/Gaps |

Every piece of identified content from all 6 sources must have a row in the matrix. Include:
- Platforms (5 entries)
- Python Packages (6 entries, grouped as "Tools" subsection)
- Research Areas (5 entries — each maps to a subpage under Research)
- Projects (5 entries — each maps to a Projects page)
- Publications (20 total: 7 papers + 13 books — list each with title, year, DOI link, target section)
- Contact info (1 entry — maps to Contact page)
- GitHub org (1 entry — maps to About → Open Source)
- Additional content found (Insights, Press Affiliate, DS-EO release notes)

### Step 3: Update `PROJECT_STATUS.md`
Mark TASK_DAL_002 as in-progress and update phase tracking.

## 7. Acceptance Criteria (G1-G4)

### G1 — Plan Approval (this gate)
- [x] Problem statement clear and grounded in spec + actual content
- [x] Taxonomy derived from existing Deepsim materials, not invented
- [x] All 6 sources identified with fetch status
- [x] IA structure matches spec §3

### G2 — Implementation Complete (Implementer → CTO)
- [ ] `docs/IA_document.md` exists with full navigation tree + page-to-content mapping + gap analysis
- [ ] `docs/content_migration_matrix.md` exists with row-by-row entry for ALL source content
- [ ] All 5 research areas explicitly documented from actual deepsim.ca content
- [ ] At least DS-AIOS and DS-EO identified as featured projects (per spec §3)
- [ ] Research taxonomy has 5–7 areas matching deepsim.ca structure

### G3 — Review Passes (Reviewer → CTO)
- [ ] IA document is coherent (no orphan pages, consistent naming)
- [ ] Migration matrix covers all identifiable content from source URLs
- [ ] Disposition classifications are justified (not arbitrary)
- [ ] Navigation structure follows WordPress menu best practices

### G4 — Final Approval (CTO)
- [ ] All acceptance criteria above met
- [ ] No research areas invented or extrapolated beyond source data
- [ ] People/Team section correctly identifies insufficient public data (not filled with speculation)
- [ ] Document is ready for TASK_DAL_003 (Visual Design System) to build on

## 8. Constraints

1. **Only classification, mapping, and documentation** — no website code or design work
2. **Research taxonomy must be derived from actual Deepsim materials** found on deepsim.ca/research/ — never invent categories
3. **People profiles use only publicly appropriate information** — no speculation about team composition
4. **All DOI links must be verified and preserved exactly** as they appear on the source pages
5. **Migration matrix must cover every identifiable content item** from all 6 sources

## 9. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Insufficient team/people content for "People" page | High | Medium | Mark as placeholder; propose expansion strategy in IA gap analysis |
| Publications have broken DOI links | Medium | Low | Verify all DOIs in migration matrix; note any dead links |
| Content too granular (too many subsections) | Medium | Medium | Consolidate packages under "Tools"; group books by series |
| News/Insights has no RSS/API feed | High | Low | Propose manual curation workflow or WordPress plugin integration in gap analysis |

## 10. Artifacts Expected

| Artifact | Path | Produced By |
|----------|------|-------------|
| IA document | `docs/IA_document.md` | Implementer |
| Content migration matrix | `docs/content_migration_matrix.md` | Implementer |
| Task directory artifacts | `docs/development/reports/TASK_DAL_002/*` | All agents per DS-EO protocol |

## 11. Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ✅ Complete | Created by CTO during TASK_DAL_001 |
| G1 (User Approval of Plan) | ✅ Approved | User approved on 2026-08-05 |
| G2 (Implementation Complete) | ⬜ Pending | Awaiting Implementer completion |
| G3 (Review Passes) | ⬜ Pending | Awaiting Reviewer assessment |
| G4 (Final Approval) | ⬜ Pending | Awaiting CTO final sign-off |

---

**CTO Plan produced by**: CTO (qwen3.6:35b)  
**Date**: 2026-08-05  
**Project**: Deepsim AI Lab WordPress Website  
**Repository**: deepsim-ai-lab


---

## Delegate Message (Full Assignment)

# DELEGATE MESSAGE — TASK_DAL_002

**From**: CTO (G1 Approved)  
**To**: Implementer  
**Phase**: S1_PLANNING → S2_IMPLEMENTATION  
**Date**: 2026-08-05  
**Priority**: P1  

## Plan Reference
- CTO_PLAN.md: `/home/deepsim/deepsim-ai-lab/docs/development/reports/TASK_DAL_002/CTO_PLAN.md`

## Assignment

The Implementer is now tasked with executing the Content Inventory + Information Architecture plan defined in TASK_DAL_002's CTO_PLAN.md.

### Deliverables
1. **IA_document.md** — Complete Information Architecture document
   - Structure all navigation levels based on content inventory
   - Map research taxonomy (5 areas) to pages
   - Define page hierarchy and cross-links
   - Include platform/package disposition decisions

2. **content_migration_matrix.md** — Content Migration Matrix
   - Row-by-row: source URL → target location → disposition (KEEP/UPDATE/MERGE/ARCHIVE/SKIP)
   - Cover all 6 reference sources from the inventory
   - Include Python package dispositions per IA document

### Requirements
- Use live data from deepsim.ca as primary source of truth (5 sources verified in inspection)
- Do NOT invent content — classify only what exists
- Respect the taxonomy: Machine Learning, Computer Vision, Data Science, IoT & Edge Intelligence, Signal & Time Series
- Preserve all 14 projects across Platforms and Projects sections

### Notes
- CTO approved plan at G1 on 2026-08-05
- All content sourced from live deepsim.ca inspection (inspection_report.md in TASK_DAL_001)
