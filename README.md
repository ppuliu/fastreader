# FastReader

**Read a book the way you browse a map — zoom out for the whole story, zoom in where it gets interesting.**

Live at [fastreader.honglei.ai](https://fastreader.honglei.ai/)

## What is FastReader

Long documents give you a bad choice: read a summary and miss the depth, or read the
whole thing and spend hours. FastReader removes the choice. Every document becomes a
stack of zoom levels — the whole book in one paragraph at the top, the full text at the
bottom, and a few honest depths in between. You zoom between them like a map, and the
part you're reading stays put while everything around it changes resolution. You never
lose your place.

Read Alice in Wonderland in 25 seconds. Zoom in when the tea party gets interesting.
Zoom back out when it doesn't.

## How to use it

### Reading

Open a document. It starts at the top level — the whole thing in one paragraph. The
dial on the right shows every level with its name and reading time.

| Input | What it does |
|---|---|
| Scroll | Read within the current level |
| Select any passage | A "dive" popover appears — click to expand that passage |
| Pinch, or hold any modifier key and scroll | Zoom in and out at your pointer |
| Double-click a paragraph | Dive into it (shift + double-click to go back up) |
| The dial: click a stop, drag, or use + / − | Jump levels directly |

Zooming in drops you exactly where you were reading: if you were 70% through a
chapter's one-paragraph version, you land 70% through its expanded scenes. A brief
gold flash marks where to keep reading.

### Adding your own documents

Click **Add a document**, paste text or load a `.txt`/`.md` file. A rewrite agent
(Claude Sonnet via the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk))
reads it, decides how many levels it deserves, writes every level, and keeps fixing its
work until it passes validation. A card shows live progress; longer documents take a
few minutes. The agent also names the levels for each document — *The Yellow Wallpaper*
came out as *In one breath → The nursery upstairs → Behind the pattern → Every word*.

### Running locally

```bash
docker build -t fastreader .
docker run -p 8000:8000 -v fastreader-data:/data \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  fastreader
# open http://localhost:8000
```

The API key is only needed for uploading new documents; the built-in library works
without it. Tests: `backend/.venv/bin/pytest backend/tests` and `cd frontend && npm test`.

## What makes FastReader interesting

**This only works because of LLMs.** Rewriting an entire book at four different depths
used to mean hiring four editors. Now it's a few minutes and a few cents of model time.
And as models get cheaper and faster, you can imagine where this goes: not four levels
but any level — a smooth dial from one sentence to the full text.

**Levels are rewrites, not summaries.** Each level reads like one continuous story at
that depth, something you could hand a friend as "the 3-minute version." It never reads
like a pile of chapter summaries stapled together.

**Zooming never loses your place.** Every paragraph knows exactly which paragraphs it
expands into one level down, and a validator checks that this mapping covers the whole
document with no gaps or overlaps. That's why zooming in and back out returns you to
the exact same spot — it's checked math, not a guess.

**An agent does the rewriting, not a single LLM call.** The agent reads the document,
decides where the natural break points are, writes the levels, and submits its work to
a validator. If validation fails, the errors go straight back to the agent and it tries
again until the document is provably well-formed. Segmentation is a decision the agent
makes per document — not a fixed template.

**The number of zoom levels is dynamic.** A short story gets 4 levels, a novel gets 5
or 6. The level names come from the rewrite itself, so the dial reads like it belongs
to that document.

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

One self-contained JSON per document, no database:

```jsonc
{
  "id": "the-yellow-wallpaper-f4a3c6",
  "title": "The Yellow Wallpaper",
  "kind": "book",                      // books render serif, papers sans
  "levels": [                          // 3 to 6 of these, decided per document
    { "name": "In one breath", "words": 106 },
    { "name": "Behind the pattern", "words": 2282 }
    // ...
  ],
  "segments": [                        // segments[level][i], reading order
    [ { "text": "…", "span": [0, 6] } ],   // span: which segments of the next
    [ { "text": "…", "span": [3, 6] } ],   // level down this one expands into
    [ { "text": "…" } ]                    // last level: the original text
  ]
}
```

`scripts/validate_data.py` checks the spans (in bounds, no gaps, no overlaps, full
coverage). `scripts/assemble.py` builds this shape from the agent's rewrites and
refuses anything invalid.

## Key design decisions and tradeoffs

**Discoverability was the hardest product problem.** The first version hid zoom behind
pinch and modifier-scroll — magical once you knew, invisible if you didn't. The fix was
several overlapping affordances: select any text and a "dive" popover appears, the dial
got always-visible + / − buttons, paragraphs show a subtle dive icon on hover, and the
hint reappears until you've actually zoomed. Power users still get the fast paths; new
users get an obvious one.

**Preprocess once, read instantly.** Processing happens at upload time (minutes), so
reading costs nothing: the whole level pyramid ships as one ~300KB fetch and every zoom
is client-side. The product bet is that a document is uploaded once and read many
times — so put all the waiting at upload, none in the reader.

**Discrete levels with a 300ms crossfade, not continuous zoom.** True map-style
continuous scaling would mean rendering two levels blended at intermediate sizes.
The directional crossfade (the old level scales toward you when diving, away when
rising) plus the landing flash buys most of the feel for a fraction of the work.

**One agent run writes the whole pyramid.** The alternative — one API call per level —
is cheaper to retry but each level stops knowing about the others. Keeping the whole
document and all levels in one context is why they read like nested tellings of the
same story. The costs: runs take minutes (mitigated by live status cards), and big
documents needed the source tool to serve pages rather than one giant blob.

**Files, not a database.** Built-in documents are JSON committed to the repo; uploads
live on a persistent volume; job status is one small JSON file per job. A database
earns its place when accounts or multiple servers arrive — the storage layer is a
30-line class, so swapping it later is cheap.

**Deploys kill in-flight processing jobs.** Accepted for now: on restart the backend
marks orphaned jobs as failed with an honest "interrupted by a server restart" message,
and dismissing a failed card deletes it for good. A durable job queue can come later.

## How I would extend this with more time

1. **Build it as a Chrome extension.** Most long-document reading happens in the
   browser — papers, blog posts, documentation. Zooming any page in place, without
   copy-pasting into an app, is where this gets genuinely useful.
2. **Fine-tune the rewrite agent.** More work on making each level maximally cohesive
   at its depth — the difference between a good rewrite and one that reads like the
   author wrote that edition themselves.
3. **Richer reading.** Keep the source's text styling, and carry images and figures
   from books and papers through to every level.
4. **[Exploration] Real-time rewriting with a very fast model.** If something like
   Haiku can rewrite on the fly as you zoom, preprocessing disappears entirely — and
   with it the fixed level count. Zoom becomes truly continuous: any passage, at any
   depth, generated the moment you ask for it.
5. **Smarter payloads for scale.** Today the reader downloads a document's entire
   level pyramid in one response — great for instant zoom, but it won't survive much
   bigger documents or slow connections. A better design: fetch only the level you're
   on plus a window around your position, prefetch the levels above and below your
   current spot (those are the only places a zoom can land), and let a CDN cache the
   immutable document chunks. The alignment spans already give every segment a stable
   address, so the API can serve any slice of any level without the client losing its
   place.
6. **Product plumbing.** User accounts and auth, PDF upload and fetch-from-URL, and a
   chat panel for asking questions about the book you're reading.

---

Design spec: `docs/superpowers/specs/2026-07-23-fastreader-design.md` ·
Implementation plan: `docs/superpowers/plans/2026-07-23-fastreader-phase1.md`
