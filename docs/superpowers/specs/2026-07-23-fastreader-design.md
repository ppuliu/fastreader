# FastReader — Design Spec

**Date:** 2026-07-23
**Status:** Approved for implementation (phase 1)
**Budget:** ~2 hours to a deployed prototype

## 1. Problem & Concept

Long documents (books, papers) take hours to read. Summaries are fast but shallow — when you
want to dig in, they abandon you. FastReader treats a document like Google Maps treats the
world: a stack of zoom levels you move between with a dial or a pinch. Each level is a **true
rewrite at that depth** — it reads as one coherent document, not a pile of bullet-point
summaries. When you zoom, the passage you're reading **stays anchored in place** while the
document changes resolution around it, exactly as the point under your cursor never moves on
a map.

**Success criterion (the 30-second wow):** a first-time viewer opens a book they know, sees it
as a single paragraph, zooms, and watches it blossom into the full text — anchored, smooth,
with the altitude dial making the depth axis legible before they touch anything.

## 2. Scope

- **Phase 1 (this build):** two preprocessed documents built in; full zoom UX; deployed to Railway.
- **Phase 2 (designed-for, not built):** user uploads; a pipeline script produces the same
  document JSON via the Claude API; persistent storage on a Railway Volume. Phase 1 decisions
  must not require rearchitecting to get there.
- **Phase 3 (out of scope entirely):** accounts, per-user libraries, sharing. First place a real
  database could enter.

## 3. UX Design

### 3.1 Library

Dark, elegant landing page with one card per document: title, author, kind (book/paper), full-text
word count, and a depth indicator ("5 levels · 30 sec → 2 hrs"). Click → reader.

### 3.2 Levels are dynamic and document-specific

- Level 0 is always a single-paragraph gist; the last level is always the verbatim full text.
- Intermediate levels: each ~3–6× the word count of the level above, snapped to the document's
  natural structure (chapters, sections) where one exists. Level *count* therefore varies:
  ~6k-word paper → 4 levels; 26k-word book → 5; 300-page novel → 6.
- Level *names* are part of the rewrite, generated per document, shown on the dial and top bar.
  - Alice (5): *In one breath · The arc · Twelve chapters · Scene by scene · Every word*
  - Attention paper (4): *Abstract of abstracts · The idea · Section by section · Full paper*
- The frontend hardcodes nothing about level count or names; it renders the document's `levels[]`.

### 3.3 Reader layout

- Centered ~65ch text column; serif for books, sans for papers. Optional segment headings render
  inline at levels aligned with named structure (e.g., chapter titles).
- Top bar: title · current level name · reading time at this level (e.g., "~6 min at this
  level"; reading time = level word count ÷ 230 wpm, shown as "30 sec" / "~6 min" / "~2 hrs").
- **Altitude dial (hybrid):** right-edge vertical rail with one labeled stop per level (name +
  word count), current stop glowing. After ~2s without pointer activity the rail fades into a slim
  pill (level name + reading time); it returns on mouse-move or zoom. Stops are
  clickable; the rail is draggable.
- First-run hint (once per document): *"Scroll to read · hold any key while scrolling (or
  double-click) to dive."*

### 3.4 Zoom inputs

| Input | Action |
|---|---|
| Plain scroll / two-finger trackpad | Pan within level (never hijacked) |
| Trackpad pinch | Zoom (arrives as `wheel` + `ctrlKey`) |
| Ctrl / ⌘ / Shift / Alt + scroll | Zoom (any modifier works; Ctrl/⌘ need `preventDefault` to stop browser zoom; macOS turns Shift+wheel into `deltaX` — treat modifier+`deltaX` as zoom delta) |
| Scroll while hovering the dial | Zoom, no modifier |
| Double-click a segment | Zoom in, anchored on it (accepted cost: no word-select on dblclick) |
| Shift + double-click | Zoom out |
| `+` / `-` keys | Zoom from viewport center |
| Dial stop click / drag | Jump to level, viewport-center anchored |

### 3.5 Anchoring semantics

- **Anchor point:** pointer y for pointer-driven zoom (wheel/pinch/double-click); viewport center
  for dial/keyboard zoom.
- **Focal segment:** the segment whose box contains the anchor y at the current level.
- **Zoom out:** land on the focal segment's parent, positioned at the anchor y.
- **Zoom in:** the focal segment maps to several children; land **proportionally** — anchor 70%
  of the way through the segment → land ~70% of the way through its children
  (index ≈ ⌊fraction × n⌋), positioned at the anchor y. Repeated zoom-in thus feels like
  continuously diving toward the sentence you were reading.
- **Landing cue:** the landing segment gets a brief gold background pulse (~700ms).

### 3.6 Transition ("altitude jump")

- ~300ms, cubic-bezier ease. Outgoing level crossfades out while scaling **toward** the viewer on
  zoom-in (scale 1 → 1.1) and **away** on zoom-out (1 → 0.94); incoming level does the reverse
  (0.94 → 1 / 1.1 → 1). Both levels mounted only during the transition.
- Zoom input during an in-flight transition is ignored.
- At the ends (zoom out at gist / in at full text): rubber-band scale bounce (~1.03 and back).
- Pinch is **discrete** (threshold per level jump), not continuous scaling. Accepted simplification.

## 4. Data Model

One self-contained JSON file per document. No database in phases 1–2.

```json
{
  "id": "alice-in-wonderland",
  "title": "Alice's Adventures in Wonderland",
  "author": "Lewis Carroll",
  "kind": "book",
  "levels": [
    { "name": "In one breath",   "words": 82 },
    { "name": "The arc",         "words": 460 },
    { "name": "Twelve chapters", "words": 1380 },
    { "name": "Scene by scene",  "words": 4100 },
    { "name": "Every word",      "words": 26400 }
  ],
  "segments": [
    [ { "text": "…", "span": [0, 5] } ],
    [ { "text": "…", "span": [0, 3] }, { "text": "…", "span": [3, 6] } ],
    [ { "heading": "II · The Pool of Tears", "text": "…", "span": [3, 6] } ],
    [ { "text": "…", "span": [12, 19] } ],
    [ { "text": "…" } ]
  ]
}
```

- `segments[L]` is reading order at level `L`; a segment has `text`, optional `heading`, and
  `span: [first, lastExclusive)` indexing into `segments[L+1]`. Last level has no spans.
- **Invariants** (enforced by `scripts/validate_data.py`, run in CI-less mode as a pre-commit
  habit and inside the build): spans are within bounds, non-empty, contiguous, and together
  exactly tile the next level (segment k's `lastExclusive` == segment k+1's `first`; first span
  starts at 0; last ends at `len(segments[L+1])`). Level 0 has exactly one segment; `levels`
  length == `segments` length.
- Parents are **derived** at load time (child index → parent index), not stored.

## 5. Architecture

### 5.1 System

```
Browser SPA (Vite + React + TS + Tailwind)
  Library · Reader = LevelView + AltitudeDial + ZoomController
  — fetches the whole document once (~300 KB, gzips ~100 KB); all zoom is client-side —
        │  GET /api/documents            → [{id, title, author, kind, levels}]
        │  GET /api/documents/{id}       → full document JSON
        ▼
FastAPI (~80 lines) — serves API + built frontend static files; SPA fallback route
        ▼
DocumentStore (~30 lines) — merges directories into one library (id → file)
  ├── data/builtin/   committed to git, ships in the image (phase 1 docs, permanent demo shelf)
  └── $DATA_DIR/documents/   (phase 2) Railway Volume for processed uploads; uploads shadow
                             built-ins on id collision; store scans at request time
```

- Phase 2 additions (no changes to the reading path): `POST /api/upload`, background task
  running `pipeline.py` (Claude API), job-status files at `$DATA_DIR/jobs/{id}.json`, volume
  mount + `ANTHROPIC_API_KEY` on Railway. Container filesystem is ephemeral on Railway —
  uploads must live on the volume.

### 5.2 Frontend state

`{ level, scrollY (native), transition?: { from, to, anchorY, landingIdx, direction } }`.
During a transition both levels render in stacked layers; on completion the old layer unmounts
and native scroll is set so the landing segment sits at the anchor y.

### 5.3 Repo layout

```
backend/app/main.py        # FastAPI + DocumentStore
frontend/                  # Vite + React + TS + Tailwind
data/builtin/*.json        # processed documents (committed)
scripts/validate_data.py   # invariant checks (§4)
Dockerfile                 # stage 1: node builds frontend → stage 2: python:slim + uvicorn
```

Deploy: Railway builds the Dockerfile; app binds `0.0.0.0:$PORT`.

## 6. Content (phase 1)

- **Alice's Adventures in Wonderland** (Gutenberg #11, public domain), 5 levels.
- **Attention Is All You Need** (arXiv 1706.03762), 4 levels; text-only — figures/tables/equations
  replaced with short bracketed inline notes at the full-text level.
- Level rewrites are **hand-generated by Claude during the build** (no API calls, no key needed),
  including spans and level names, then checked by `validate_data.py`. Quality bar: each level
  must read as one continuous document at that depth — no bullet lists, no "this chapter
  covers…" summarese.
- Phase 2's `pipeline.py` reproduces this process programmatically; it is **not** built today.

## 7. Testing

1. `scripts/validate_data.py` over all of `data/builtin/` — the invariants in §4.
2. API smoke test (list + fetch endpoints, 404 on unknown id).
3. Browser walkthrough before declaring done (driven via orca): every level of both documents,
   zoom in/out at top/middle/bottom anchors, dial, keys, double-click, end-of-range bounce;
   screenshot each state.

## 8. Build Order

1. Scaffold (repo layout, FastAPI, Vite/React/Tailwind, Dockerfile) with a stub document.
2. Alice JSON (hand-generated) + validator.
3. Reader: level rendering + dial + level switching (no animation).
4. Anchored zoom: input scheme, focal/anchor math, altitude-jump transition, landing pulse.
5. Paper JSON; library page; polish (typography, hint, reading times, pill-fade dial).
6. Deploy to Railway; browser walkthrough on the deployed URL.

## 9. Cut List (today)

Uploads/pipeline (phase 2), figures & equations, mobile polish, continuous pinch scaling,
auto-play intro zoom (stretch: only if everything above lands early).

## 10. Risks & Mitigations

- **Transition jank at full-text level** (~800 paragraphs in the layer): render transition layers
  with `will-change: transform, opacity`; if still janky, cap the outgoing layer to the visible
  slice. Accept minor imperfection — the demo lives mostly in levels 0–3.
- **`preventDefault` on ctrl/⌘ wheel** requires a non-passive listener on the reader container —
  easy to get silently wrong; verify in the walkthrough (§7.3).
- **Hand-generated spans drift from full text** — the validator makes this loud, not silent.
- **Railway build time** (node + python multi-stage) — keep images slim; not on the demo path.
