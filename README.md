# FastReader

**Read long documents the way Google Maps reads the world.**
Live at [fastreader.honglei.ai](https://fastreader.honglei.ai/)

## What is FastReader

Long documents force a bad choice: read a summary (fast, but shallow — and when you
want to dig in, it abandons you) or read the whole thing (deep, but hours). FastReader
removes the choice by treating a document like a map: a stack of zoom levels you move
between freely, where **the passage you're reading stays anchored in place while the
document changes resolution around it** — the way the point under your cursor never
moves when you zoom a map.

Every document becomes a pyramid of **true rewrites**: a one-paragraph gist at the top,
a narrative overview below it, chapter- or section-depth levels under that, down to the
verbatim full text. Each level reads as one continuous document at that depth — flowing
prose, not bullet points, not chunk-by-chunk summaries. You can read the whole book in
25 seconds, or 3 minutes, or 26 minutes, or in full — and switch between those readings
mid-sentence without losing your place.

## How to use it

### Reading

Open a document. It starts at the gist — the entire document as a single paragraph. The
**altitude dial** on the right edge shows every level with its name and word count; it
fades to a slim pill while you read and returns when you move the mouse.

| Input | What it does |
|---|---|
| Scroll / two-finger swipe | Read within the current level (never hijacked) |
| Pinch, or any modifier key + scroll | Zoom — the paragraph under your pointer stays put |
| Double-click a paragraph | Dive into it (shift + double-click to rise) |
| `+` / `-` keys | Zoom from the center of the screen |
| Scroll over the dial, click or drag a stop | Jump levels directly |

Zooming in lands you *proportionally*: if you were 70% of the way through a chapter's
one-paragraph rendition, you land 70% of the way through its expanded scenes. Repeated
dives feel like falling continuously toward the sentence you were reading. A brief gold
pulse marks where your eyes should land after each jump.

### Adding your own documents

Click **Add a document**, paste text or load a `.txt`/`.md` file, and give it a title.
A rewrite agent (Claude Sonnet via the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk))
reads the document, plans how many levels it deserves, writes every level, and keeps
revising until the result passes the alignment validator. A processing card shows live
status; expect a few minutes for longer documents. When it finishes, the document
appears in the library with level names the agent invented for it — *The Yellow
Wallpaper* came out as *In one breath → The nursery upstairs → Behind the pattern →
Every word*.

### Running locally

```bash
# backend (serves the API and, in production, the built frontend)
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
BUILTIN_DIR=data/builtin backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000

# frontend dev server (proxies /api to :8000)
cd frontend && npm install && npm run dev
```

Tests: `backend/.venv/bin/pytest backend/tests` · `cd frontend && npm test`

Uploads work locally without an API key if you're logged into Claude Code (the Agent
SDK rides its auth); deployed environments need `ANTHROPIC_API_KEY`.

## What makes FastReader interesting

**Levels are rewrites, not summaries.** Most "summarize at three lengths" tools produce
disconnected chunk summaries. FastReader's quality bar is that every level *reads as one
document* — present-tense continuous prose you could hand someone as "the 3-minute
edition." The zoom feels like changing altitude over the same terrain, not switching
between different artifacts.

**The alignment pyramid is what makes anchoring honest.** Every segment at level *N*
carries a `span: [first, lastExclusive)` into level *N+1*, and the spans of a level must
exactly tile the level below — no gaps, no overlaps, machine-checked. Anchoring is then
just arithmetic: zoom out walks to the parent, zoom in picks a child proportionally.
The invariant is strong enough that a zoom-in → zoom-out round trip returns you to the
*exact same scroll position*.

**The rewrite agent is gated by a validator, not by vibes.** The agent's only way to
finish is a `submit_rewrites` tool that runs the assembler and the span validator;
errors bounce straight back into its loop until the document is provably well-formed.
Creative output, mechanically verified — the same invariants that guarded the
hand-written phase-1 documents now guard every user upload.

**Levels are per-document, in count and in name.** A 6k-word story gets 4 levels, a
novel gets 5 or 6, and the level names are part of the rewrite itself — the dial reads
like it belongs to *this* document, not like generic UI chrome.

**Zoom is instant because the whole pyramid ships at once.** One ~300KB JSON fetch per
document; every zoom afterwards is pure client-side math and a 300ms crossfade. No
spinners inside the reading experience, ever.

**Plain scroll is sacred.** Reading input is never hijacked; zoom lives on pinch, *any*
modifier + scroll (whichever you reach for works), double-click, keys, and the dial.

## Architecture

<!-- TODO: excalidraw diagram goes here -->

```
Browser SPA (Vite + React + TS + Tailwind)
  Library · Reader = LevelView + AltitudeDial + ZoomController
  — whole document fetched once; all zooming is client-side —
        │  GET /api/documents · GET /api/documents/{id}
        │  POST /api/upload · GET/DELETE /api/jobs/{id}
        ▼
FastAPI backend
  ├── DocumentStore — merges data/builtin/ (shipped in the image)
  │                   with $DATA_DIR/documents/ (Railway volume)
  ├── JobStore — one JSON status file per processing job
  └── background task → scripts/pipeline.py
        └── Claude Agent SDK (Sonnet) with two in-process tools:
            get_source (numbered paragraphs + level plan)
            submit_rewrites (assemble + validate; errors retry the loop)
```

The document format (one self-contained JSON per document, no database):

```jsonc
{
  "id": "the-yellow-wallpaper-f4a3c6",
  "title": "The Yellow Wallpaper",
  "kind": "book",                      // serif rendering; "paper" renders sans
  "levels": [                          // dynamic count — 3 to 6
    { "name": "In one breath", "words": 106 },
    { "name": "Behind the pattern", "words": 2282 }
    // ...
  ],
  "segments": [                        // segments[level][i], reading order
    [ { "text": "…", "span": [0, 6] } ],          // spans index the next level down
    [ { "text": "…", "heading": "II", "span": [3, 6] } ],
    [ { "text": "…" } ]                            // last level: verbatim, no spans
  ]
}
```

`scripts/validate_data.py` enforces the invariants (spans in bounds, contiguous, exactly
tiling the next level; single gist segment; level/segment parity). The assembler
(`scripts/assemble.py`) turns agent- or hand-written rewrites plus the chunked source
into this shape, and refuses anything invalid.

## Key design decisions and tradeoffs

**Whole-document fetch over lazy level loading.** ~300KB (≈100KB gzipped) buys
zero-latency zoom, which is the product's soul. Revisit only when documents get ~10×
bigger.

**Discrete levels with a 300ms "altitude jump," not continuous scaling.** True
Maps-style continuous zoom would mean rendering two levels at intermediate scales —
beautiful, and an afternoon of work by itself. The directional crossfade (outgoing level
scales *toward* you when diving, *away* when rising) plus the landing pulse fake most of
the feel at a fraction of the cost.

**Files, not a database.** Built-ins are committed JSON shipped in the image; uploads
live on a Railway volume; job status is one JSON file per job. A database earns its
place only with accounts or multiple replicas — the `DocumentStore` seam is where it
would slot in.

**One agent run writes the whole pyramid.** The alternative — one API call per level —
is cheaper to retry but loses cross-level coherence. Keeping the entire document and all
levels in a single Sonnet context is why the levels read like nested tellings of the
same story. Tradeoff: multi-minute runs, mitigated by live status and a validating
retry loop instead of one-shot prayer.

**Sonnet, not Opus, for rewrites.** The rewrite task is well-specified and
validator-gated; Sonnet's speed/cost fits a per-upload loop. The prompt and validator
carry the quality bar.

**`span` ranges instead of child-ID lists.** Contiguity is the core invariant; a
`[first, lastExclusive)` range can't even express a violation of it. Parents are derived
at load time, never stored — one source of truth for alignment.

**Deploys kill in-flight processing jobs.** Accepted for a prototype: on startup the
backend marks orphaned jobs failed with an honest "interrupted by a server restart"
message, and Dismiss deletes them server-side. A durable queue is phase-3 territory.

**Double-click zooms instead of selecting words.** Google Maps semantics won over
text-selection convention; a reading prototype favors navigation. Selection still works
for drag-selection.

**Assumes a single replica.** File-based stores and in-process background tasks are
consistent only with one instance — fine at this scale, and the first thing to change
if it ever isn't.

---

Design spec: `docs/superpowers/specs/2026-07-23-fastreader-design.md` ·
Implementation plan: `docs/superpowers/plans/2026-07-23-fastreader-phase1.md`
