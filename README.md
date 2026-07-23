# FastReader

Read long documents like Google Maps reads the world. Every document is a pyramid of true
rewrites — a one-paragraph gist, a narrative overview, chapter/section levels, down to the
verbatim full text. Zoom with a pinch, any modifier + scroll, double-click, or the altitude
dial; the passage you're reading stays anchored in place while the document changes
resolution around it.

## Run locally

```bash
# backend (serves API + built frontend)
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
BUILTIN_DIR=data/builtin backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000

# frontend dev server (proxies /api to :8000)
cd frontend && npm install && npm run dev
```

Tests: `backend/.venv/bin/pytest backend/tests` · `cd frontend && npm test`

## Data pipeline

Documents are self-contained JSON files in `data/builtin/` (no database). To rebuild:

```bash
backend/.venv/bin/python scripts/fetch_alice.py     # Gutenberg -> data/work/alice_sections.json
backend/.venv/bin/python scripts/fetch_paper.py     # arXiv HTML -> data/work/paper_sections.json
# hand-written level rewrites live in data/work/*_rewrites.json
backend/.venv/bin/python -m scripts.assemble data/work/alice_rewrites.json data/work/alice_sections.json data/builtin/alice-in-wonderland.json
backend/.venv/bin/python scripts/validate_data.py data/builtin/*.json
```

The validator enforces the alignment invariants (spans contiguous, full coverage) that make
anchored zoom correct.

## Deploy

Railway builds the `Dockerfile` as-is; the app binds `0.0.0.0:$PORT`. Phase 2 (user uploads)
adds a Railway Volume mounted at `DATA_DIR` plus an `ANTHROPIC_API_KEY` for the rewrite
pipeline — the `DocumentStore` already merges `$DATA_DIR/documents/` over `data/builtin/`.

Design spec: `docs/superpowers/specs/2026-07-23-fastreader-design.md`
