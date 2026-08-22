# G1 → G2 Handoff — TASK_DAL_016

**Task ID**: TASK_DAL_016  
**Handoff Date**: 2026-08-19  
**From**: CTO 🏗️ | **To**: Implementer-dal  

---

## Approved Scope (G1)

All deliverables approved as-is. No modifications to scope, constraints, or acceptance criteria.

## Phase B Deliverable: Illustration Set (6 SVGs)

**Output path for ALL files**:  
`/home/deepsim/deepsim-ai-lab/wp-content/themes/twentytwentyfive/assets/illustrations/`

(All subdirectories must be created as part of this work.)

### 1. `hero-wavelet.svg`
- **Description**: Abstract wavelet signal decomposition — layered sine waves with threshold lines and envelope curves. Represents deepsim's signal processing research identity.
- **viewBox**: 800x400
- **Colors**: Brand accent `#1A73E8`, secondary text `#6E6E73`, surface `#F5F5F7`, borders `#D2D2D7`
- **Style**: Clean line-art, no fills except transparent/white bg. Wave lines at varying amplitudes with dashed threshold line.

### 2. `neural-network.svg`
- **Description**: Minimal neural network topology — nodes (filled circles) + connections (straight lines). NOT a stock-photo style brain graphic. Technical schematic aesthetic.
- **viewBox**: 600x350
- **Colors**: Brand accent `#1A73E8` for active nodes, tertiary `#F5A623` for connection paths, secondary text `#6E6E73` for labels
- **Style**: Layer architecture visible (input → hidden → output layers with vertical groupings)

### 3. `signal-processing.svg`
- **Description**: Signal processing pipeline block diagram: [Input Signal] → [Preprocessing] → [Feature Extraction] → [Output]. Blocks connected by arrows with labels on connections.
- **viewBox**: 700x200
- **Colors**: Data viz primary `#4A90D9` (block fills), secondary `#7CB342` (arrow labels), brand accent `#1A73E8` (input/output blocks)
- **Style**: Rectangular blocks with rounded corners, directional arrows between them

### 4. `iot-sensor.svg`
- **Description**: IoT sensor network topology: USV node connected to multiple sensor nodes + ground station. Shows communication links between elements.
- **viewBox**: 650x300
- **Colors**: Semantic colors — green `#0B8A00` for verified/active sensors, brand accent `#1A73E8` for USV, tertiary `#F5A623` for pending items, borders `#D2D2D7` for links
- **Style**: Node-and-link diagram with circular nodes and labeled connections

### 5. `research-flow.svg`
- **Description**: Research methodology flowchart: [Hypothesis] → [Experiment Design] → [Data Collection] → [Analysis] → [Publication]. Sequential process with decision diamond for iteration loop.
- **viewBox**: 900x250
- **Colors**: Sequential data viz palette `#4A90D9` → `#7CB342` → `#F5A623` per stage, borders `#D2D2D7`
- **Style**: Flowchart with rounded rectangles and diamond decision node. Dashed iteration arrow back to Experiment Design.

### 6. `logo-mark-abstract.svg`
- **Description**: Abstract geometric brand mark for hero/About sections — not the WordPress logo. Geometric composition using deepsim research identity (converging lines, layered shapes suggesting data/signal).
- **viewBox**: 200x200
- **Colors**: Brand accent `#1A73E8` on transparent background (`<rect width="100%" height="100%" fill="none"/>`)
- **Style**: Geometric, minimal — clean shapes conveying precision and research

## Global Constraints (MUST satisfy ALL)

1. **Palette only**: Every color hex must match TASK_DAL_003 §3 palette. No new colors.
2. **No gradients**: `<linearGradient>` or `<radialGradient>` must NOT appear in any file.
3. **Accessibility**: Each SVG MUST include `<title>` and `<desc>` elements.
4. **File size**: Each SVG under 15KB uncompressed (`wc -c` check).
5. **Inline markers**: All files tagged with `// TASK_DAL_016 Task N:` comments.
6. **Hand-written SVG**: No export from design tools. Clean, minimal SVG markup.

## CSS Integration (Subtask 4 — also in this phase)

Create: `/home/deepsim/deepsim-ai-lab/wp-content/themes/twentytwentyfive/assets/css/illustrations.css`

Required utility classes:
- `.svg-illustration-hero` — hero SVG container (responsive sizing, max-width: 100%, height: auto)
- `.svg-chart-container` — chart display sizing
- `.pattern-bg-grid` / `.pattern-bg-lines` — subtle pattern background rules
- SVG responsive default: `max-width: 100%; height: auto; display: inline-block;`

## CSS Pattern Assets (Subtask 4 continued)

Create in same directory:
- `/home/deepsim/deepsim-ai-lab/wp-content/themes/twentytwentyfive/assets/patterns/grid-dots.svg` — subtle dot grid (8px spacing, low opacity via stroke-opacity)
- `/home/deepsim/deepsim-ai-lab/wp-content/themes/twentytwentyfive/assets/patterns/micro-lines.svg` — diagonal micro-crosshatch pattern

## Acceptance Criteria for This G2 Phase

| # | Criterion | Method |
|---|-----------|--------|
| AC-1 | All 6 SVGs + 2 patterns + CSS file exist on disk | ls verification |
| AC-2 | All colors match TASK_DAL_003 §3 palette | grep hex codes |
| AC-3 | No gradients in any SVG | grep `<linearGradient\|<radialGradient` — should find nothing |
| AC-4 | Each SVG has `<title>` and `<desc>` | DOM inspection |
| AC-5 | Each file under 15KB | `wc -c` |
| AC-6 | All files tagged with TASK_DAL_016 markers | grep marker text |

## What NOT to Do

- ❌ Modify any existing theme PHP/HTML/CSS files outside of the new `assets/` directory
- ❌ Create SVGs with gradients, drop shadows, or heavy fill patterns
- ❌ Use stock imagery aesthetics (photorealistic, 3D rendered looks)
- ❌ Include text labels smaller than 10px font-size in any SVG
- ❌ Add JavaScript interactivity

## Deliverable Report Format

After completing implementation, produce an inline report:
```
TASK_DS_EO_XXX Implementation Status
=====================================
Task N: [APPLIED | FAILED: <reason>]
- File: path/to/file, line ~N (SVG viewBox)
- Change: one-line summary
...
```
