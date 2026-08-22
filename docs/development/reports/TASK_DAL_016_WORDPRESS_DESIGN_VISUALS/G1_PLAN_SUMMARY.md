# G1 Plan Summary — TASK_DAL_016: WordPress Design Visual Enhancement via SVG Illustrations

**Task ID**: TASK_DAL_016  
**Project**: deepsim-ai-lab (DAL)  
**Producer**: CTO 🏗️ (ollama/qwen3.6:35b)  
**Date**: 2026-08-19  
**Gate**: G1 — Plan Review  

---

## 1. Context & Scope

### Existing Artifacts (Pre-Existing, NOT to Be Modified)
- `docs/design_system.md` — Full design system from TASK_DAL_003: typography, colors, spacing, grids, nav specs, page templates
- `Deepsim_AI_Lab_Website_Plan.md` — Original product spec
- `wp-content/themes/twentytwentyfive/` — WordPress Twenty Twenty-Five theme (unmodified default)
- Content inventory from TASK_DAL_002

### What This Task Covers
Add **visual richness** to the deepsim-ai-lab website through:
1. **Custom SVG illustrations** — research lab, wavelet/signal processing, neural computation graphics
2. **Data visualizations** — charts, diagrams for research pages
3. **System architecture graphics** — SVG-based infrastructure/flow diagrams
4. **Research-specific imagery** — domain-appropriate scientific figures

### What This Task Explicitly Does NOT Cover
- ❌ Dark mode overhaul (design system already has both modes)
- ❌ Theme modifications or new theme creation
- ❌ Content changes or rewrites
- ❌ WordPress core/plugin updates
- ❌ Color palette changes
- ❌ Typography changes
- ❌ Navigation layout changes

**Design principle**: Preserve existing architecture. Augment with SVG visual assets only.

---

## 2. Architecture Decision

### Delivery Model: Static SVG Assets + CSS Utility Classes

SVG files are **static deliverables** — no JavaScript, no frameworks, no build step. They live in the WordPress theme's `assets/` directory and are referenced via standard `<img src="...">` or `background-image` CSS rules.

```
/home/deepsim/deepsim-ai-lab/wp-content/themes/twentytwentyfive/assets/
├── illustrations/        # Custom SVG illustrations
│   ├── hero-wavelet.svg           # Hero section: wavelet decomposition
│   ├── neural-network.svg         # Neural computation graphic
│   ├── signal-processing.svg      # Signal processing pipeline
│   ├── iot-sensor.svg             # IoT/IoV sensor diagram
│   ├── research-flow.svg          # Research methodology flow
│   └── logo-mark-abstract.svg     # Abstract lab brand mark
├── diagrams/              # System architecture & data viz SVGs
│   ├── system-architecture.svg    # Full system architecture
│   ├── water-monitoring-stack.svg # USV platform stack diagram
│   ├── plant-detection-pipeline.svg # ML pipeline for plant detection
│   └── river-health-model.svg     # River health estimation model
├── charts/               # Data visualization SVGs
│   ├── accuracy-comparison.svg    # Model performance comparison
│   ├── research-publications-chart.svg  # Publication stats
│   └── funding-timeline.svg       # Project timeline chart
└── patterns/              # Subtle background patterns
    ├── grid-dots.svg              # Academic grid pattern
    └── micro-lines.svg            # Technical crosshatch pattern
```

### Design Token Integration
All SVG colors reference the existing design system palette (TASK_DAL_003 §3):
- Brand accent: `#1A73E8` / `#4A9EFF` (dark)
- Data viz primary: `#4A90D9`, secondary: `#7CB342`, tertiary: `#F5A623`
- Text: `#1D1D1F` / `#E5E5EA`
- Surfaces: `#F5F5F7` / `#1C1C1E`
- Borders: `#D2D2D7` / `#38383A`

No new colors. No gradients. SVG stroke widths, fill patterns, and opacities conform to the existing palette.

### CSS Integration
Minimal CSS additions in `functions.php` or a custom stylesheet for:
- `.svg-illustration-hero` — hero-section SVG container rules
- `.svg-chart-container` — chart display sizing
- `.pattern-bg-grid` / `.pattern-bg-lines` — subtle pattern backgrounds
- SVG responsive handling (`max-width: 100%; height: auto`)

---

## 3. Task Breakdown

### Subtask 1: Illustration Set (Hero + Research Areas)
**Deliverable**: 6 custom SVG illustrations  
**Pages targeted**: Homepage hero section, Research area cards

| # | SVG File | Description | Color Palette Usage | Size Target |
|---|----------|-------------|---------------------|-------------|
| 1.1 | `hero-wavelet.svg` | Abstract wavelet signal decomposition — layered sine waves with threshold lines | Brand accent + secondary text color | 800x400 viewBox |
| 1.2 | `neural-network.svg` | Minimal neural network topology — nodes (circles) + connections (lines), not stock-photo style | Brand accent for active nodes, tertiary for paths | 600x350 viewBox |
| 1.3 | `signal-processing.svg` | Signal processing pipeline: input → preprocessing → feature extraction → output (block diagram) | Primary data viz colors per block | 700x200 viewBox |
| 1.4 | `iot-sensor.svg` | IoT sensor network topology with nodes representing USV, sensors, ground station | Semantic colors for different node types | 650x300 viewBox |
| 1.5 | `research-flow.svg` | Research methodology flowchart: hypothesis → experiment → analysis → publication | Sequential data viz palette | 900x250 viewBox |
| 1.6 | `logo-mark-abstract.svg` | Abstract geometric brand mark for hero/About sections (not the WordPress logo) | Brand accent on transparent BG | 200x200 viewBox |

### Subtask 2: Architecture & System Diagrams
**Deliverable**: 4 system-level SVG diagrams  
**Pages targeted**: Research pages, Projects pages

| # | SVG File | Description | Color Palette Usage | Size Target |
|---|----------|-------------|---------------------|-------------|
| 2.1 | `system-architecture.svg` | Full deepsim AI lab system architecture (sensor layer → USV → cloud → analysis) | Semantic + brand palette | 1000x500 viewBox |
| 2.2 | `water-monitoring-stack.svg` | USV water monitoring platform technical stack diagram | Per-layer semantic colors | 600x450 viewBox |
| 2.3 | `plant-detection-pipeline.svg` | Plant detection ML pipeline (image capture → preprocessing → segmentation → classification) | Sequential data viz palette | 800x400 viewBox |
| 2.4 | `river-health-model.svg` | River health estimation model architecture | Data viz primary/secondary | 700x350 viewBox |

### Subtask 3: Data Visualization Charts
**Deliverable**: 3 publication/performance charts  
**Pages targeted**: Publications page, Research pages

| # | SVG File | Description | Color Palette Usage | Size Target |
|---|----------|-------------|---------------------|-------------|
| 3.1 | `accuracy-comparison.svg` | Bar chart comparing model accuracies across research areas | Data viz primary/secondary/tertiary | 500x300 viewBox |
| 3.2 | `research-publications-chart.svg` | Publication count by year (line chart with data points) | Brand accent line, secondary text for labels | 600x350 viewBox |
| 3.3 | `funding-timeline.svg` | Project timeline with milestones | Semantic colors per milestone type | 900x200 viewBox |

### Subtask 4: Background Patterns + CSS Integration
**Deliverable**: Pattern SVGs + CSS rules  
**Pages targeted**: Global

| # | Asset | Description | Usage |
|---|-------|-------------|-------|
| 4.1 | `grid-dots.svg` | Subtle dot grid (8px spacing, low opacity) | Section backgrounds for research areas |
| 4.2 | `micro-lines.svg` | Diagonal micro-crosshatch pattern | Card surfaces on specific sections |
| 4.3 | CSS additions | `.svg-illustration-*`, `.pattern-bg-*` utility classes + SVG responsive rules | functions.php or assets/css/illustrations.css |

---

## 4. Implementation Rules (R-SI from source inspection protocol)

1. **No new dependencies** — Pure SVG files only, no JS libraries
2. **Existing palette only** — Every color in every SVG must match TASK_DAL_003 §3 palette
3. **No gradients** — Per design constraint §10: solid fills and strokes only
4. **Accessible** — All SVGs include `<title>` and `<desc>` tags; no color-only information
5. **Responsive** — viewBox-based, max-width 100% via CSS utility class
6. **File size limit** — Each SVG under 15KB uncompressed (clean hand-written SVG, not export from design tools)
7. **Inline change markers** — All files tagged with `// TASK_DAL_016` comments

---

## 5. Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| AC-1 | All 13 SVGs exist on disk in correct directory structure | `ls` verification |
| AC-2 | All SVG colors match design system palette (no new hex values) | grep color values against TASK_DAL_003 §3 |
| AC-3 | No gradients in any SVG (`<linearGradient>`, `<radialGradient>` absent) | grep check |
| AC-4 | Each SVG has `<title>` and `<desc>` for accessibility | DOM inspection |
| AC-5 | Each SVG under 15KB uncompressed | `wc -c` verification |
| AC-6 | CSS utility classes added to theme | functions.php or assets/css/illustrations.css exists with rules |
| AC-7 | All existing design system specs unchanged (zero diff on non-assets) | git diff shows only new files under `assets/` |
| AC-8 | SVGs render correctly at all breakpoints (verified via HTML test page) | Visual inspection |

---

## 6. Model Pressure Plan

| Phase | Required Models | Always Unload |
|-------|-----------------|---------------|
| CTO planning (this phase) | qwen3.6:35b, nomic-embed-text | ornith:35b, laguna-xs-2.1, qwen3.8:27b |
| Implementation | qwen3.6:35b, qwen3.8:27b, nomic-embed-text | ornith:35b, laguna-xs-2.1 |
| Review | laguna-xs-2.1, qwen3.6:35b, nomic-embed-text | qwen3.8:27b, ornith:35b |
| Idle | nomic-embed-text only | all large models |

---

## 7. Estimated Effort

| Subtask | SVGs | Est. Time (CPU-only) | Complexity |
|---------|------|----------------------|------------|
| 1. Illustration set | 6 | ~45 min total | Medium — requires careful composition |
| 2. Architecture diagrams | 4 | ~35 min total | Low-Medium — more schematic, less artistic |
| 3. Charts | 3 | ~20 min total | Low — data visualization is formulaic |
| 4. CSS + patterns | 2 patterns + CSS | ~15 min | Low |
| **Total** | **15 assets** | **~115 min** | **Medium** |

---

## 8. Pre-G1 Verification Checklist

- [x] Design system (TASK_DAL_003) exists with complete color palette and constraints
- [x] WordPress installation present at `/home/deepsim/deepsim-ai-lab/` with Twenty Twenty-Five theme
- [x] Content inventory (TASK_DAL_002) provides content reference for illustration subjects
- [x] No existing SVG illustration directory in theme
- [x] `assets/` subdirectory does not yet exist under twentytwentyfive — this task creates it
