# FastReader Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deployed prototype where a reader zooms through true multi-level rewrites of Alice in Wonderland and the Transformer paper with Google-Maps-style anchoring.

**Architecture:** React SPA fetches one self-contained multi-level JSON per document from a ~80-line FastAPI backend and does all zooming client-side. Documents are pyramids of segments linked by contiguous `span` ranges; a validator enforces the alignment invariants. Multi-stage Docker image deploys to Railway.

**Tech Stack:** Python 3.12, FastAPI, pytest · Node 22, Vite, React 18+, TypeScript, Tailwind v4, vitest · Docker, Railway.

**Spec:** `docs/superpowers/specs/2026-07-23-fastreader-design.md` (authoritative for UX semantics).

## Global Constraints

- No database. Documents are JSON files. `DocumentStore` merges `data/builtin/` + optional `$DATA_DIR/documents/` (later shadows earlier by id).
- Exactly two API endpoints: `GET /api/documents`, `GET /api/documents/{id}`. No router in the SPA (state-switch between Library and Reader).
- Level 0 = single gist segment; last level = verbatim full text (no `span`). `span = [first, lastExclusive)` into the next level; spans tile the next level exactly.
- Frontend hardcodes nothing about level count or names.
- Plain scroll is NEVER hijacked; only modifier+wheel / pinch / dial / dblclick / ± zoom.
- Zoom input during an in-flight transition (300 ms) is ignored.
- Dark theme: bg `#0d0e14`, text `#d7d9e0`, gold accent `#d4b45a`. Books render serif (`Georgia, 'Iowan Old Style', serif`), papers sans.
- Reading time = words ÷ 230 wpm ("30 sec" / "~6 min" / "~1.9 hrs" formats via `readingTime()`).
- `python3` + venv at `backend/.venv`; run backend commands from repo root as shown.
- Every data JSON must pass `scripts/validate_data.py` before it is committed.

---

### Task 1: Backend — validator, DocumentStore, API

**Files:**
- Create: `scripts/validate_data.py`
- Create: `backend/app/__init__.py` (empty), `backend/app/store.py`, `backend/app/main.py`
- Create: `backend/requirements.txt`, `backend/requirements-dev.txt`
- Test: `backend/tests/test_validate.py`, `backend/tests/test_api.py`, `backend/tests/conftest.py`

**Interfaces:**
- Produces: `validate_document(doc: dict) -> list[str]` (error strings, empty = valid) in `scripts/validate_data.py`; CLI `python scripts/validate_data.py <files...>` exits 1 on any error.
- Produces: `DocumentStore(dirs: list[str|Path])` with `.list() -> list[dict]` (summaries: id/title/author/kind/levels) and `.get(doc_id) -> dict | None`.
- Produces: HTTP API consumed by Task 2's `api.ts`. Env vars: `BUILTIN_DIR` (default `data/builtin`), `DATA_DIR` (optional), `STATIC_DIR` (default `frontend/dist`).

- [ ] **Step 1: Scaffold + install deps**

```bash
mkdir -p backend/app backend/tests scripts data/builtin
touch backend/app/__init__.py
```

`backend/requirements.txt`:
```
fastapi>=0.115
uvicorn>=0.30
```

`backend/requirements-dev.txt`:
```
pytest>=8
httpx>=0.27
```

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

- [ ] **Step 2: Write failing validator tests**

`backend/tests/conftest.py`:
```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))          # for scripts.validate_data
sys.path.insert(0, str(ROOT / "backend"))  # for app.*


def make_doc(**over):
    doc = {
        "id": "stub", "title": "Stub", "author": "A", "kind": "book",
        "levels": [
            {"name": "Gist", "words": 4},
            {"name": "Mid", "words": 8},
            {"name": "Full", "words": 20},
        ],
        "segments": [
            [{"text": "the whole thing", "span": [0, 2]}],
            [{"text": "first half", "span": [0, 2]},
             {"text": "second half", "span": [2, 5]}],
            [{"text": "p1"}, {"text": "p2"}, {"text": "p3"}, {"text": "p4"}, {"text": "p5"}],
        ],
    }
    doc.update(over)
    return doc
```

`backend/tests/test_validate.py`:
```python
from conftest import make_doc
from scripts.validate_data import validate_document


def test_valid_doc_passes():
    assert validate_document(make_doc()) == []


def test_level_zero_must_have_one_segment():
    doc = make_doc()
    doc["segments"][0].append({"text": "extra", "span": [0, 0]})
    assert any("level 0" in e for e in validate_document(doc))


def test_span_gap_detected():
    doc = make_doc()
    doc["segments"][1][1]["span"] = [3, 5]  # gap: 2 uncovered
    assert any("contiguous" in e for e in validate_document(doc))


def test_span_must_cover_next_level_fully():
    doc = make_doc()
    doc["segments"][1][1]["span"] = [2, 4]  # tail p5 uncovered
    assert any("cover" in e for e in validate_document(doc))


def test_last_level_must_not_have_spans():
    doc = make_doc()
    doc["segments"][2][0]["span"] = [0, 1]
    assert any("last level" in e for e in validate_document(doc))


def test_missing_span_on_mid_level():
    doc = make_doc()
    del doc["segments"][1][0]["span"]
    assert any("missing span" in e for e in validate_document(doc))


def test_levels_segments_length_mismatch():
    doc = make_doc()
    doc["levels"].pop()
    assert any("levels" in e for e in validate_document(doc))
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `backend/.venv/bin/pytest backend/tests/test_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.validate_data'`

- [ ] **Step 4: Implement the validator**

`scripts/validate_data.py`:
```python
"""Validate FastReader document JSON invariants (spec §4)."""
import json
import sys
from pathlib import Path


def validate_document(doc: dict) -> list[str]:
    errors = []
    for key in ("id", "title", "author", "kind", "levels", "segments"):
        if key not in doc:
            errors.append(f"missing top-level key: {key}")
    if errors:
        return errors
    levels, segments = doc["levels"], doc["segments"]
    if len(levels) != len(segments):
        return [f"levels ({len(levels)}) and segments ({len(segments)}) lengths differ"]
    if len(levels) < 2:
        return ["need at least 2 levels"]
    if len(segments[0]) != 1:
        errors.append(f"level 0 must have exactly one segment, has {len(segments[0])}")
    last = len(segments) - 1
    for L, segs in enumerate(segments):
        if not segs:
            errors.append(f"L{L}: empty level")
            continue
        for i, seg in enumerate(segs):
            if not str(seg.get("text", "")).strip():
                errors.append(f"L{L}[{i}]: empty text")
            if L == last:
                if "span" in seg:
                    errors.append(f"L{L}[{i}]: last level must not have spans")
                continue
            span = seg.get("span")
            if not (isinstance(span, list) and len(span) == 2):
                errors.append(f"L{L}[{i}]: missing span")
                continue
            s, e = span
            if e <= s:
                errors.append(f"L{L}[{i}]: empty span {span}")
        if L == last or any("missing span" in x or "empty span" in x for x in errors):
            continue
        if segs[0]["span"][0] != 0:
            errors.append(f"L{L}: first span must start at 0")
        for i in range(len(segs) - 1):
            if segs[i]["span"][1] != segs[i + 1]["span"][0]:
                errors.append(
                    f"L{L}[{i}]→[{i+1}]: spans not contiguous "
                    f"({segs[i]['span']} then {segs[i+1]['span']})")
        if segs[-1]["span"][1] != len(segments[L + 1]):
            errors.append(
                f"L{L}: spans must cover next level exactly "
                f"(end {segs[-1]['span'][1]} != {len(segments[L + 1])})")
        actual = sum(len(str(seg["text"]).split()) for seg in segs)
        declared = levels[L].get("words", 0)
        if declared and abs(actual - declared) / max(actual, 1) > 0.25:
            print(f"  warning: L{L} declared {declared} words, actual {actual}")
    return errors


def main(paths: list[str]) -> int:
    failed = False
    for p in paths:
        doc = json.loads(Path(p).read_text())
        errs = validate_document(doc)
        status = "OK" if not errs else "INVALID"
        print(f"{p}: {status}")
        for e in errs:
            print(f"  - {e}")
        failed = failed or bool(errs)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Also create `scripts/__init__.py` (empty) so `scripts.validate_data` imports.

- [ ] **Step 5: Run validator tests, verify pass**

Run: `backend/.venv/bin/pytest backend/tests/test_validate.py -v`
Expected: 7 passed

- [ ] **Step 6: Write failing API/store tests**

`backend/tests/test_api.py`:
```python
import json

import pytest
from fastapi.testclient import TestClient

from conftest import make_doc


@pytest.fixture()
def client(tmp_path, monkeypatch):
    builtin = tmp_path / "builtin"
    builtin.mkdir()
    (builtin / "stub.json").write_text(json.dumps(make_doc()))
    uploads_root = tmp_path / "uploads"
    (uploads_root / "documents").mkdir(parents=True)
    shadow = make_doc(title="Shadowed Stub")
    (uploads_root / "documents" / "stub.json").write_text(json.dumps(shadow))
    other = make_doc(id="other", title="Other")
    (uploads_root / "documents" / "other.json").write_text(json.dumps(other))
    monkeypatch.setenv("BUILTIN_DIR", str(builtin))
    monkeypatch.setenv("DATA_DIR", str(uploads_root))
    import importlib
    from app import main as main_mod
    importlib.reload(main_mod)
    return TestClient(main_mod.app)


def test_list_returns_summaries_without_segments(client):
    docs = client.get("/api/documents").json()
    ids = {d["id"] for d in docs}
    assert ids == {"stub", "other"}
    for d in docs:
        assert "segments" not in d
        assert d["levels"][0]["name"] == "Gist"


def test_data_dir_shadows_builtin(client):
    docs = {d["id"]: d for d in client.get("/api/documents").json()}
    assert docs["stub"]["title"] == "Shadowed Stub"


def test_get_returns_full_document(client):
    doc = client.get("/api/documents/stub").json()
    assert len(doc["segments"]) == 3


def test_unknown_id_404(client):
    assert client.get("/api/documents/nope").status_code == 404
```

- [ ] **Step 7: Run API tests, verify they fail**

Run: `backend/.venv/bin/pytest backend/tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 8: Implement store and app**

`backend/app/store.py`:
```python
import json
from pathlib import Path

SUMMARY_KEYS = ("id", "title", "author", "kind", "levels")


class DocumentStore:
    """Merges document directories; later directories shadow earlier by id."""

    def __init__(self, dirs):
        self.dirs = [Path(d) for d in dirs if d]

    def _scan(self) -> dict[str, Path]:
        found: dict[str, Path] = {}
        for d in self.dirs:
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.json")):
                found[p.stem] = p
        return found

    def list(self) -> list[dict]:
        out = []
        for path in self._scan().values():
            doc = json.loads(path.read_text())
            out.append({k: doc[k] for k in SUMMARY_KEYS})
        return out

    def get(self, doc_id: str):
        path = self._scan().get(doc_id)
        return json.loads(path.read_text()) if path else None
```

`backend/app/main.py`:
```python
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.store import DocumentStore

ROOT = Path(__file__).resolve().parents[2]
BUILTIN_DIR = os.environ.get("BUILTIN_DIR", str(ROOT / "data" / "builtin"))
DATA_DIR = os.environ.get("DATA_DIR")
STATIC_DIR = os.environ.get("STATIC_DIR", str(ROOT / "frontend" / "dist"))

store = DocumentStore(
    [BUILTIN_DIR] + ([str(Path(DATA_DIR) / "documents")] if DATA_DIR else []))

app = FastAPI(title="FastReader")


@app.get("/api/documents")
def list_documents():
    return store.list()


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    doc = store.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


if Path(STATIC_DIR).is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

Note: the store rescans per request (a handful of files — trivially cheap) so phase-2 uploads appear without restart. The env-var reads at module top are why the test reloads the module.

- [ ] **Step 9: Run all backend tests, verify pass**

Run: `backend/.venv/bin/pytest backend/tests -v`
Expected: 11 passed

- [ ] **Step 10: Commit**

```bash
git add scripts/ backend/
git commit -m "feat: backend API, DocumentStore, and data validator"
```

---

### Task 2: Frontend scaffold + document math library

**Files:**
- Create: `frontend/` (Vite react-ts scaffold), `frontend/vite.config.ts` (modify scaffold), `frontend/src/index.css` (replace)
- Create: `frontend/src/lib/doc.ts`, `frontend/src/api.ts`
- Create: `data/builtin/stub.json` (temporary; deleted in Task 3)
- Test: `frontend/src/lib/doc.test.ts`

**Interfaces:**
- Consumes: Task 1 API endpoints.
- Produces (used by Tasks 4–5, exact signatures):
  - Types `Segment {text; heading?; span?}`, `LevelMeta {name; words}`, `FastDoc {id; title; author; kind: 'book'|'paper'; levels: LevelMeta[]; segments: Segment[][]}`, `DocSummary = Omit<FastDoc,'segments'>`
  - `deriveParents(doc: FastDoc): number[][]` — `parents[L][i]` = parent index at level L−1; `parents[0] = []`
  - `landingIndex(doc, parents, from, to, focalIdx, fraction): number` — multi-level capable
  - `readingTime(words: number): string`
  - `fetchSummaries(): Promise<DocSummary[]>`, `fetchDoc(id): Promise<FastDoc>`

- [ ] **Step 1: Scaffold Vite + Tailwind v4 + vitest**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install && npm install tailwindcss @tailwindcss/vite && npm install -D vitest && cd ..
```

`frontend/vite.config.ts` (replace):
```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
});
```

In `frontend/package.json` scripts add: `"test": "vitest run"`.
Replace `frontend/src/index.css` entirely with (Task 5 appends keyframes):
```css
@import "tailwindcss";

:root { color-scheme: dark; }
body { background: #0d0e14; color: #d7d9e0; }
```
Delete `frontend/src/App.css`.

- [ ] **Step 2: Write failing doc.ts tests**

`frontend/src/lib/doc.test.ts`:
```ts
import { describe, expect, it } from 'vitest';
import { deriveParents, landingIndex, readingTime, type FastDoc } from './doc';

const doc: FastDoc = {
  id: 't', title: 'T', author: 'A', kind: 'book',
  levels: [
    { name: 'Gist', words: 4 },
    { name: 'Mid', words: 8 },
    { name: 'Full', words: 20 },
  ],
  segments: [
    [{ text: 'all', span: [0, 2] }],
    [{ text: 'a', span: [0, 2] }, { text: 'b', span: [2, 5] }],
    [{ text: 'p1' }, { text: 'p2' }, { text: 'p3' }, { text: 'p4' }, { text: 'p5' }],
  ],
};

describe('deriveParents', () => {
  it('maps children to parent indices', () => {
    const p = deriveParents(doc);
    expect(p[0]).toEqual([]);
    expect(p[1]).toEqual([0, 0]);
    expect(p[2]).toEqual([0, 0, 1, 1, 1]);
  });
});

describe('landingIndex', () => {
  const parents = deriveParents(doc);
  it('zoom in lands proportionally within children', () => {
    expect(landingIndex(doc, parents, 0, 1, 0, 0.0)).toBe(0);
    expect(landingIndex(doc, parents, 0, 1, 0, 0.6)).toBe(1);
  });
  it('zoom in clamps to last child', () => {
    expect(landingIndex(doc, parents, 1, 2, 1, 0.99)).toBe(4);
  });
  it('zoom out lands on parent', () => {
    expect(landingIndex(doc, parents, 2, 1, 3, 0.5)).toBe(1);
  });
  it('multi-level zoom dives through', () => {
    expect(landingIndex(doc, parents, 0, 2, 0, 0.5)).toBe(2);
    expect(landingIndex(doc, parents, 2, 0, 4, 0.5)).toBe(0);
  });
});

describe('readingTime', () => {
  it('formats seconds, minutes, hours', () => {
    expect(readingTime(82)).toBe('20 sec');
    expect(readingTime(1380)).toBe('~6 min');
    expect(readingTime(26400)).toBe('~1.9 hrs');
  });
});
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `cd frontend && npm test`
Expected: FAIL — cannot resolve `./doc`

- [ ] **Step 4: Implement doc.ts and api.ts**

`frontend/src/lib/doc.ts`:
```ts
export interface Segment { text: string; heading?: string; span?: [number, number]; }
export interface LevelMeta { name: string; words: number; }
export interface FastDoc {
  id: string; title: string; author: string; kind: 'book' | 'paper';
  levels: LevelMeta[]; segments: Segment[][];
}
export type DocSummary = Omit<FastDoc, 'segments'>;

export function deriveParents(doc: FastDoc): number[][] {
  const parents: number[][] = doc.segments.map(() => []);
  for (let L = 0; L < doc.segments.length - 1; L++) {
    doc.segments[L].forEach((seg, i) => {
      const [s, e] = seg.span!;
      for (let c = s; c < e; c++) parents[L + 1][c] = i;
    });
  }
  return parents;
}

export function landingIndex(
  doc: FastDoc, parents: number[][], from: number, to: number,
  focalIdx: number, fraction: number,
): number {
  let idx = focalIdx;
  let f = fraction;
  let L = from;
  while (L < to) {
    const [s, e] = doc.segments[L][idx].span!;
    const n = e - s;
    const raw = f * n;
    idx = Math.min(e - 1, s + Math.floor(raw));
    f = raw - Math.floor(raw); // carry sub-position into the next dive
    L++;
  }
  while (L > to) { idx = parents[L][idx]; L--; }
  return idx;
}

export function readingTime(words: number): string {
  const mins = words / 230;
  if (mins < 1) return `${Math.max(5, Math.round((mins * 60) / 5) * 5)} sec`;
  if (mins < 60) return `~${Math.round(mins)} min`;
  return `~${(mins / 60).toFixed(1)} hrs`;
}
```

`frontend/src/api.ts`:
```ts
import type { DocSummary, FastDoc } from './lib/doc';

export async function fetchSummaries(): Promise<DocSummary[]> {
  const r = await fetch('/api/documents');
  if (!r.ok) throw new Error(`list failed: ${r.status}`);
  return r.json();
}

export async function fetchDoc(id: string): Promise<FastDoc> {
  const r = await fetch(`/api/documents/${id}`);
  if (!r.ok) throw new Error(`fetch ${id} failed: ${r.status}`);
  return r.json();
}
```

- [ ] **Step 5: Run tests, verify pass**

Run: `cd frontend && npm test`
Expected: 6 passed (3 describe blocks)

- [ ] **Step 6: End-to-end smoke with a stub document**

Create `data/builtin/stub.json`:
```json
{
  "id": "stub", "title": "Stub Doc", "author": "Nobody", "kind": "book",
  "levels": [{ "name": "Gist", "words": 4 }, { "name": "Full", "words": 10 }],
  "segments": [
    [{ "text": "a tiny stub document", "span": [0, 2] }],
    [{ "text": "first full paragraph here" }, { "text": "second full paragraph here" }]
  ]
}
```

```bash
backend/.venv/bin/python scripts/validate_data.py data/builtin/stub.json
cd frontend && npm run build && cd ..
BUILTIN_DIR=data/builtin backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000 &
sleep 2 && curl -s localhost:8000/api/documents | head -c 300; curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/
kill %1
```
Expected: `stub.json: OK`, JSON summary list, and `200` for the static index.

- [ ] **Step 7: Commit**

```bash
git add frontend/ data/builtin/stub.json
git commit -m "feat: frontend scaffold, document math lib, end-to-end stub"
```

---

### Task 3: Alice content — fetch, hand-write levels, assemble

**Files:**
- Create: `scripts/fetch_alice.py`, `scripts/assemble.py`
- Create: `data/work/alice_rewrites.json` (hand-generated at execution time)
- Create: `data/builtin/alice-in-wonderland.json` (generated)
- Delete: `data/builtin/stub.json`
- Test: `backend/tests/test_assemble.py`

**Interfaces:**
- Consumes: `validate_document` from Task 1.
- Produces: work-file format `{"sections": [{"title": str, "paragraphs": [str]}]}`; rewrites format (below); `python scripts/assemble.py <rewrites> <work> <out>` used again by Task 6.

**Rewrites file format** (shared with Task 6):
```json
{
  "id": "...", "title": "...", "author": "...", "kind": "book",
  "level_names": ["...", "...", "...", "...", "..."],
  "gist": "single paragraph text",
  "mids": [
    { "segments": [ { "text": "...", "heading": "optional", "units": 3 } ] }
  ]
}
```
`mids` are the intermediate levels top-down (`len(level_names) == len(mids) + 2`). `units` = how many segments of the *next level down* this segment covers, consumed contiguously in order; the last mid's units count full-text paragraphs. The full-text level is built from the work file (paragraphs flattened in order; each section's title becomes `heading` on its first paragraph).

- [ ] **Step 1: Write failing assembler test**

`backend/tests/test_assemble.py`:
```python
from scripts.assemble import assemble
from scripts.validate_data import validate_document

WORK = {"sections": [
    {"title": "One", "paragraphs": ["p1 words here", "p2 words here"]},
    {"title": "Two", "paragraphs": ["p3 words here"]},
]}
REWRITES = {
    "id": "t", "title": "T", "author": "A", "kind": "book",
    "level_names": ["Gist", "Mid", "Full"],
    "gist": "the whole tiny thing",
    "mids": [{"segments": [
        {"text": "covers section one", "heading": "One", "units": 2},
        {"text": "covers section two", "heading": "Two", "units": 1},
    ]}],
}


def test_assemble_produces_valid_doc():
    doc = assemble(REWRITES, WORK)
    assert validate_document(doc) == []
    assert doc["levels"][0]["words"] == 4
    assert doc["segments"][2][0]["heading"] == "One"
    assert doc["segments"][2][2]["heading"] == "Two"
    assert doc["segments"][0][0]["span"] == [0, 2]
    assert doc["segments"][1][1]["span"] == [2, 3]


def test_assemble_rejects_bad_unit_totals():
    bad = {**REWRITES,
           "mids": [{"segments": [{"text": "x", "units": 1},
                                  {"text": "y", "units": 1}]}]}
    try:
        assemble(bad, WORK)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
```

- [ ] **Step 2: Run test, verify it fails**

Run: `backend/.venv/bin/pytest backend/tests/test_assemble.py -v`
Expected: FAIL — no module `scripts.assemble`

- [ ] **Step 3: Implement assembler**

`scripts/assemble.py`:
```python
"""Assemble a FastReader document from hand-written rewrites + extracted full text."""
import json
import sys
from pathlib import Path

from scripts.validate_data import validate_document


def _words(text: str) -> int:
    return len(text.split())


def assemble(rewrites: dict, work: dict) -> dict:
    sections = work["sections"]
    full_segs = []
    for sec in sections:
        for j, para in enumerate(sec["paragraphs"]):
            seg = {"text": para}
            if j == 0 and sec.get("title"):
                seg["heading"] = sec["title"]
            full_segs.append(seg)

    mids = rewrites["mids"]
    if len(rewrites["level_names"]) != len(mids) + 2:
        raise ValueError("level_names must be len(mids) + 2")

    levels_segs = []           # built bottom-up: full text, then mids upward
    below = full_segs
    for mid in reversed(mids):
        cursor = 0
        segs = []
        for m in mid["segments"]:
            seg = {"text": m["text"], "span": [cursor, cursor + m["units"]]}
            if m.get("heading"):
                seg["heading"] = m["heading"]
            segs.append(seg)
            cursor += m["units"]
        if cursor != len(below):
            raise ValueError(
                f"units sum {cursor} != next level length {len(below)} "
                f"(level '{m.get('text', '?')[:30]}…')")
        levels_segs.append(below)
        below = segs
    levels_segs.append(below)
    levels_segs.append([{"text": rewrites["gist"], "span": [0, len(below)]}])
    levels_segs.reverse()      # now top-down: gist, mids…, full

    doc = {
        "id": rewrites["id"], "title": rewrites["title"],
        "author": rewrites["author"], "kind": rewrites["kind"],
        "levels": [
            {"name": name, "words": sum(_words(s["text"]) for s in segs)}
            for name, segs in zip(rewrites["level_names"], levels_segs)
        ],
        "segments": levels_segs,
    }
    errs = validate_document(doc)
    if errs:
        raise ValueError("assembled doc invalid:\n" + "\n".join(errs))
    return doc


if __name__ == "__main__":
    rewrites_p, work_p, out_p = sys.argv[1:4]
    doc = assemble(json.loads(Path(rewrites_p).read_text()),
                   json.loads(Path(work_p).read_text()))
    Path(out_p).write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print(f"wrote {out_p}: {len(doc['levels'])} levels, "
          f"{[l['words'] for l in doc['levels']]} words")
```

- [ ] **Step 4: Run test, verify pass**

Run: `backend/.venv/bin/pytest backend/tests/test_assemble.py -v`
Expected: 2 passed

- [ ] **Step 5: Fetch and parse Alice**

`scripts/fetch_alice.py`:
```python
"""Download Alice from Gutenberg and parse into sections/paragraphs."""
import json
import re
import urllib.request
from pathlib import Path

URL = "https://www.gutenberg.org/cache/epub/11/pg11.txt"
OUT = Path("data/work/alice_sections.json")

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
         "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}


def main():
    raw = urllib.request.urlopen(URL).read().decode("utf-8")
    body = raw.split("*** START", 1)[1].split("***", 1)[1]
    body = body.split("*** END", 1)[0]
    # Chapter headings look like: "CHAPTER I.\nDown the Rabbit-Hole"
    parts = re.split(r"\nCHAPTER ([IVX]+)\.\n([^\n]+)\n", body)
    assert len(parts) == 1 + 3 * 12, f"expected 12 chapters, got {(len(parts)-1)//3}"
    sections = []
    for k in range(1, len(parts), 3):
        numeral, title, text = parts[k], parts[k + 1].strip(), parts[k + 2]
        paras = [re.sub(r"\s+", " ", p).strip()
                 for p in re.split(r"\n\s*\n", text)]
        paras = [p for p in paras if p and not p.startswith("THE END")]
        sections.append({"title": f"{numeral} · {title}", "paragraphs": paras})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"sections": sections}, ensure_ascii=False, indent=1))
    for s in sections:
        print(f"{s['title']}: {len(s['paragraphs'])} paras, "
              f"{sum(len(p.split()) for p in s['paragraphs'])} words")
    print(f"TOTAL paras: {sum(len(s['paragraphs']) for s in sections)}")


if __name__ == "__main__":
    main()
```

Run: `backend/.venv/bin/python scripts/fetch_alice.py`
Expected: 12 chapters listed with paragraph counts, total ~800. If the assert fires, inspect `raw[:3000]` and adjust the heading regex to the actual Gutenberg formatting — do not hand-edit the text.

- [ ] **Step 6: Hand-write `data/work/alice_rewrites.json`** *(content-generation step — the executing agent writes this)*

Structure (fixed):
- `level_names`: `["In one breath", "The arc", "Twelve chapters", "Scene by scene", "Every word"]`
- `gist`: one paragraph, 70–95 words.
- `mids[0]` "The arc": 5 segments, ~80–110 words each, `units` = chapters covered (contiguous, sum = 12; suggested 3+2+3+2+2 — adjust to narrative shape).
- `mids[1]` "Twelve chapters": 12 segments (one per chapter, in order), ~100–130 words each, `heading` = the chapter title from the fetch output (e.g. `"I · Down the Rabbit-Hole"`), `units` = scenes for that chapter (2–4 each, total ~34–38).
- `mids[2]` "Scene by scene": one segment per scene, ~90–130 words each, `units` = full-text paragraphs covered; per chapter the scene units must sum to that chapter's paragraph count from the Step 5 output. `heading` only on each chapter's first scene (same chapter title).

Quality bar (spec §6): every level reads as one continuous narrative in present tense — no bullet lists, no "in this chapter", no "we then see". Each segment must be a faithful condensation of exactly the text its span covers (respect scene boundaries: pick paragraph split points at actual scene shifts).

Verify: `backend/.venv/bin/python -m scripts.assemble data/work/alice_rewrites.json data/work/alice_sections.json data/builtin/alice-in-wonderland.json` (run from repo root; `-m` puts the root on `sys.path` so `scripts.validate_data` imports)
Expected: `wrote … 5 levels, [~82, ~460, ~1400, ~4000, ~26000] words` and no ValueError. Iterate on the rewrites until clean.

- [ ] **Step 7: Validate, remove stub, commit**

```bash
backend/.venv/bin/python scripts/validate_data.py data/builtin/alice-in-wonderland.json
git rm data/builtin/stub.json
git add scripts/ data/work/ data/builtin/alice-in-wonderland.json backend/tests/test_assemble.py
git commit -m "feat: Alice in Wonderland multi-level document + assembler"
```
(Note: Task 2's Step 6 smoke test is the stub's only consumer; nothing else references it.)

---

### Task 4: Reader core — library, level rendering, dial, plain switching

**Files:**
- Create: `frontend/src/components/Library.tsx`, `frontend/src/components/Reader.tsx`, `frontend/src/components/LevelView.tsx`, `frontend/src/components/AltitudeDial.tsx`
- Modify: `frontend/src/App.tsx` (replace scaffold content)

**Interfaces:**
- Consumes: Task 2 types + api + `readingTime`.
- Produces (Task 5 extends these, do not rename):
  - `LevelView({ segments, kind, pulseIdx }: { segments: Segment[]; kind: 'book'|'paper'; pulseIdx?: number | null })` — each segment wrapped in `<div data-seg={i}>`
  - `AltitudeDial({ levels, current, active, onJump }: { levels: LevelMeta[]; current: number; active: boolean; onJump: (level: number) => void })`
  - `Reader({ doc, onBack }: { doc: FastDoc; onBack: () => void })` with internal `requestZoom(target: number, clientY: number | null)`

- [ ] **Step 1: LevelView**

`frontend/src/components/LevelView.tsx`:
```tsx
import type { Segment } from '../lib/doc';

export function LevelView({ segments, kind, pulseIdx }:
  { segments: Segment[]; kind: 'book' | 'paper'; pulseIdx?: number | null }) {
  return (
    <div className={`mx-auto max-w-[68ch] px-6 pt-14 pb-[45vh] ${
      kind === 'book' ? "font-[Georgia,'Iowan_Old_Style',serif]" : 'font-sans'}`}>
      {segments.map((s, i) => (
        <div key={i} data-seg={i} className={pulseIdx === i ? 'seg-pulse' : ''}>
          {s.heading && (
            <h2 className="mt-10 mb-4 text-[13px] font-sans tracking-[0.18em] uppercase text-[#8b8f9e]">
              {s.heading}
            </h2>
          )}
          <p className="mb-5 text-[17.5px] leading-[1.8]">{s.text}</p>
        </div>
      ))}
    </div>
  );
}
```
(`pb-[45vh]` lets the last segment reach viewport center for anchoring.)

- [ ] **Step 2: AltitudeDial (rail + pill, driven by `active` prop)**

`frontend/src/components/AltitudeDial.tsx`:
```tsx
import type { LevelMeta } from '../lib/doc';
import { readingTime } from '../lib/doc';

const fmtWords = (w: number) =>
  w >= 1000 ? `${(w / 1000).toFixed(w < 10000 ? 1 : 0)}k` : `${w}`;

export function AltitudeDial({ levels, current, active, onJump }:
  { levels: LevelMeta[]; current: number; active: boolean; onJump: (level: number) => void }) {
  return (
    <div data-dial className="fixed right-5 top-1/2 -translate-y-1/2 z-20 select-none">
      {/* rail */}
      <div className={`flex flex-col items-end gap-6 transition-opacity duration-500 ${
        active ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
        {levels.map((l, i) => (
          <button key={i} onClick={() => onJump(i)}
            className="group flex items-center gap-2.5 cursor-pointer">
            <span className={`text-[11px] font-sans text-right transition-colors ${
              i === current ? 'text-[#e8dca8] font-semibold' : 'text-[#6d6d7c] group-hover:text-[#a5a8b5]'}`}>
              {l.name} · {fmtWords(l.words)} words
            </span>
            <span className={`rounded-full transition-all ${
              i === current
                ? 'w-3.5 h-3.5 bg-[#d4b45a] shadow-[0_0_12px_#d4b45a88]'
                : 'w-2 h-2 bg-[#3a3d4d] group-hover:bg-[#565a6e]'}`} />
          </button>
        ))}
      </div>
      {/* pill */}
      <div className={`absolute right-0 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-full
        border border-[#2e2e3c] bg-[#1d1d28]/80 px-4 py-1.5 text-[12px] font-sans text-[#cfc9a6]
        transition-opacity duration-500 ${active ? 'opacity-0' : 'opacity-100'}`}>
        ◈ {levels[current].name} · {readingTime(levels[current].words)}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Reader (plain level switching this task; zoom lands in Task 5)**

`frontend/src/components/Reader.tsx`:
```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FastDoc } from '../lib/doc';
import { deriveParents, readingTime } from '../lib/doc';
import { LevelView } from './LevelView';
import { AltitudeDial } from './AltitudeDial';

export function Reader({ doc, onBack }: { doc: FastDoc; onBack: () => void }) {
  const [level, setLevel] = useState(0);
  const [dialActive, setDialActive] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const idleTimer = useRef<number>(0);
  const parents = useMemo(() => deriveParents(doc), [doc]);
  void parents; // used by requestZoom in Task 5

  const poke = useCallback(() => {
    setDialActive(true);
    window.clearTimeout(idleTimer.current);
    idleTimer.current = window.setTimeout(() => setDialActive(false), 2000);
  }, []);
  useEffect(() => { poke(); return () => window.clearTimeout(idleTimer.current); }, [poke]);

  const requestZoom = useCallback((target: number, clientY: number | null) => {
    void clientY; // anchoring added in Task 5
    if (target < 0 || target >= doc.levels.length || target === level) return;
    setLevel(target);
    scrollRef.current?.scrollTo({ top: 0 });
  }, [doc, level]);

  return (
    <div className="fixed inset-0 flex flex-col bg-[#0d0e14]" onPointerMove={poke}>
      <header className="z-10 flex items-center justify-between border-b border-[#1e2029] px-5 py-3 font-sans">
        <div className="flex items-center gap-4 min-w-0">
          <button onClick={onBack} className="text-[#6d6d7c] hover:text-[#d7d9e0] cursor-pointer">←</button>
          <span className="truncate text-[13px] tracking-[0.14em] uppercase text-[#8b8f9e]">{doc.title}</span>
        </div>
        <span className="text-[12px] text-[#b8a24a] whitespace-nowrap">
          {doc.levels[level].name} · {readingTime(doc.levels[level].words)}
        </span>
      </header>
      <div className="relative flex-1 min-h-0">
        <div ref={scrollRef} className="reader-scroll h-full overflow-y-auto">
          <LevelView segments={doc.segments[level]} kind={doc.kind} />
        </div>
        <AltitudeDial levels={doc.levels} current={level} active={dialActive}
          onJump={(l) => requestZoom(l, null)} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Library + App**

`frontend/src/components/Library.tsx`:
```tsx
import type { DocSummary } from '../lib/doc';
import { readingTime } from '../lib/doc';

export function Library({ docs, onOpen }:
  { docs: DocSummary[]; onOpen: (id: string) => void }) {
  return (
    <div className="min-h-screen px-6 py-16 font-sans">
      <h1 className="mx-auto max-w-3xl text-3xl font-semibold tracking-tight">FastReader</h1>
      <p className="mx-auto mt-2 max-w-3xl text-[#8b8f9e]">
        Read at any altitude. Every level is a true rewrite — zoom without losing your place.
      </p>
      <div className="mx-auto mt-10 grid max-w-3xl gap-5 sm:grid-cols-2">
        {docs.map((d) => {
          const full = d.levels[d.levels.length - 1];
          return (
            <button key={d.id} onClick={() => onOpen(d.id)}
              className="rounded-xl border border-[#23232e] bg-[#12121a] p-6 text-left
                         transition-colors hover:border-[#3a3d4d] cursor-pointer">
              <div className="text-[11px] uppercase tracking-[0.16em] text-[#6d6d7c]">{d.kind}</div>
              <div className={`mt-2 text-xl text-[#e6e7ee] ${d.kind === 'book' ? "font-[Georgia,serif]" : ''}`}>
                {d.title}
              </div>
              <div className="mt-1 text-sm text-[#8b8f9e]">{d.author}</div>
              <div className="mt-4 text-[12px] text-[#b8a24a]">
                {d.levels.length} levels · {readingTime(d.levels[0].words)} → {readingTime(full.words)}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

`frontend/src/App.tsx` (replace entirely):
```tsx
import { useEffect, useState } from 'react';
import { fetchDoc, fetchSummaries } from './api';
import type { DocSummary, FastDoc } from './lib/doc';
import { Library } from './components/Library';
import { Reader } from './components/Reader';

export default function App() {
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [open, setOpen] = useState<FastDoc | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { fetchSummaries().then(setDocs).catch((e) => setError(String(e))); }, []);
  if (error) return <div className="p-10 font-sans text-red-400">{error}</div>;
  if (open) return <Reader doc={open} onBack={() => setOpen(null)} />;
  return <Library docs={docs} onOpen={(id) => fetchDoc(id).then(setOpen).catch((e) => setError(String(e)))} />;
}
```
Also simplify `frontend/src/main.tsx` if the scaffold references App.css (keep only `index.css` import).

- [ ] **Step 5: Verify in dev servers**

```bash
BUILTIN_DIR=data/builtin backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000 &
cd frontend && npm run dev &
```
Open `http://localhost:5173`: library shows Alice card; click → gist paragraph; dial shows 5 named stops with word counts; clicking stops switches levels; after 2 s idle the rail fades to the pill and returns on mouse-move. Chapter headings visible at levels 2+.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: library, reader with level rendering and altitude dial"
```

---

### Task 5: Anchored zoom, altitude-jump transition, input scheme

**Files:**
- Create: `frontend/src/hooks/useZoomInput.ts`
- Modify: `frontend/src/components/Reader.tsx` (extend Task 4 version), `frontend/src/components/AltitudeDial.tsx` (add wheel-to-zoom), `frontend/src/index.css` (append keyframes)

**Interfaces:**
- Consumes: `landingIndex`, `deriveParents`, Task 4 components.
- Produces: `useZoomInput(containerRef, onStep: (dir: 1|-1, clientY: number|null) => void)`; `AltitudeDial` gains `onStep: (dir: 1 | -1) => void` prop.

- [ ] **Step 1: Append animation CSS**

Append to `frontend/src/index.css`:
```css
.anim-out-in   { animation: frOutIn 300ms cubic-bezier(.4,0,.2,1) both; }
.anim-in-in    { animation: frInIn 300ms cubic-bezier(.4,0,.2,1) both; }
.anim-out-out  { animation: frOutOut 300ms cubic-bezier(.4,0,.2,1) both; }
.anim-in-out   { animation: frInOut 300ms cubic-bezier(.4,0,.2,1) both; }
@keyframes frOutIn  { from { opacity: 1; transform: scale(1); }    to { opacity: 0; transform: scale(1.1); } }
@keyframes frInIn   { from { opacity: 0; transform: scale(.94); }  to { opacity: 1; transform: scale(1); } }
@keyframes frOutOut { from { opacity: 1; transform: scale(1); }    to { opacity: 0; transform: scale(.94); } }
@keyframes frInOut  { from { opacity: 0; transform: scale(1.1); }  to { opacity: 1; transform: scale(1); } }

.seg-pulse { animation: frPulse 900ms ease-out both; border-radius: 6px; }
@keyframes frPulse { from { background: rgba(212,180,90,.26); } to { background: transparent; } }

.edge-bounce { animation: frBounce 250ms ease-out both; }
@keyframes frBounce { 0% { transform: scale(1); } 40% { transform: scale(1.025); } 100% { transform: scale(1); } }
```
(Naming: `anim-{layer}-{zoomDirection}` — e.g. `anim-out-in` = outgoing layer during zoom-in.)

- [ ] **Step 2: useZoomInput hook**

`frontend/src/hooks/useZoomInput.ts`:
```ts
import { useEffect, type RefObject } from 'react';

/** dir: 1 = dive deeper (level+1), -1 = rise. clientY null = viewport center. */
export function useZoomInput<T extends HTMLElement>(
  containerRef: RefObject<T | null>,
  onStep: (dir: 1 | -1, clientY: number | null) => void,
) {
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let acc = 0;
    let lastWheel = 0;
    const wheel = (e: WheelEvent) => {
      if (!(e.ctrlKey || e.metaKey || e.shiftKey || e.altKey)) return; // plain scroll: untouched
      e.preventDefault();
      const now = performance.now();
      if (now - lastWheel > 250) acc = 0;
      lastWheel = now;
      acc += e.deltaY !== 0 ? e.deltaY : e.deltaX; // macOS shift+wheel arrives as deltaX
      if (Math.abs(acc) >= 60) {
        onStep(acc < 0 ? 1 : -1, e.clientY); // pinch-out / scroll-up = dive
        acc = 0;
      }
    };
    const dbl = (e: MouseEvent) => {
      e.preventDefault();
      onStep(e.shiftKey ? -1 : 1, e.clientY);
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === '+' || e.key === '=') onStep(1, null);
      else if (e.key === '-') onStep(-1, null);
    };
    el.addEventListener('wheel', wheel, { passive: false });
    el.addEventListener('dblclick', dbl);
    window.addEventListener('keydown', key);
    return () => {
      el.removeEventListener('wheel', wheel);
      el.removeEventListener('dblclick', dbl);
      window.removeEventListener('keydown', key);
    };
  }, [containerRef, onStep]);
}
```

- [ ] **Step 3: Dial wheel-to-zoom + drag (replace `AltitudeDial.tsx` entirely)**

Adds `onStep` prop, a non-passive wheel listener (no modifier needed over the dial), and rail drag (spec §3.3):

```tsx
import { useEffect, useRef } from 'react';
import type { LevelMeta } from '../lib/doc';
import { readingTime } from '../lib/doc';

const fmtWords = (w: number) =>
  w >= 1000 ? `${(w / 1000).toFixed(w < 10000 ? 1 : 0)}k` : `${w}`;

export function AltitudeDial({ levels, current, active, onJump, onStep }:
  { levels: LevelMeta[]; current: number; active: boolean;
    onJump: (level: number) => void; onStep: (dir: 1 | -1) => void }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const railRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    let acc = 0;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      acc += e.deltaY;
      if (Math.abs(acc) >= 60) { onStep(acc > 0 ? 1 : -1); acc = 0; } // scroll down = deeper
    };
    el.addEventListener('wheel', wheel, { passive: false });
    return () => el.removeEventListener('wheel', wheel);
  }, [onStep]);

  const dragTo = (clientY: number) => {
    const rail = railRef.current;
    if (!rail) return;
    const r = rail.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (clientY - r.top) / r.height));
    const idx = Math.round(frac * (levels.length - 1));
    if (idx !== current) onJump(idx);
  };

  return (
    <div ref={rootRef} data-dial className="fixed right-5 top-1/2 -translate-y-1/2 z-20 select-none">
      {/* rail */}
      <div ref={railRef}
        onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); dragTo(e.clientY); }}
        onPointerMove={(e) => { if (e.buttons === 1) dragTo(e.clientY); }}
        className={`flex flex-col items-end gap-6 transition-opacity duration-500 ${
          active ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
        {levels.map((l, i) => (
          <button key={i} onClick={() => onJump(i)}
            className="group flex items-center gap-2.5 cursor-pointer">
            <span className={`text-[11px] font-sans text-right transition-colors ${
              i === current ? 'text-[#e8dca8] font-semibold' : 'text-[#6d6d7c] group-hover:text-[#a5a8b5]'}`}>
              {l.name} · {fmtWords(l.words)} words
            </span>
            <span className={`rounded-full transition-all ${
              i === current
                ? 'w-3.5 h-3.5 bg-[#d4b45a] shadow-[0_0_12px_#d4b45a88]'
                : 'w-2 h-2 bg-[#3a3d4d] group-hover:bg-[#565a6e]'}`} />
          </button>
        ))}
      </div>
      {/* pill */}
      <div className={`absolute right-0 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-full
        border border-[#2e2e3c] bg-[#1d1d28]/80 px-4 py-1.5 text-[12px] font-sans text-[#cfc9a6]
        transition-opacity duration-500 ${active ? 'opacity-0' : 'opacity-100'}`}>
        ◈ {levels[current].name} · {readingTime(levels[current].words)}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Reader — anchoring + transition (replace Task 4's `requestZoom` and render)**

Replace `Reader.tsx` internals with:
```tsx
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { FastDoc } from '../lib/doc';
import { deriveParents, landingIndex, readingTime } from '../lib/doc';
import { LevelView } from './LevelView';
import { AltitudeDial } from './AltitudeDial';
import { useZoomInput } from '../hooks/useZoomInput';

interface Trans {
  from: number; to: number; anchorY: number; landingIdx: number;
  dir: 'in' | 'out'; frozenScroll: number;
}

function findFocal(container: HTMLElement, anchorClientY: number) {
  const segs = Array.from(container.querySelectorAll<HTMLElement>('[data-seg]'));
  let idx = 0, fraction = 0.5, bestDist = Infinity;
  for (let i = 0; i < segs.length; i++) {
    const r = segs[i].getBoundingClientRect();
    if (anchorClientY >= r.top && anchorClientY <= r.bottom) {
      return { idx: i, fraction: (anchorClientY - r.top) / Math.max(1, r.height) };
    }
    const d = Math.min(Math.abs(anchorClientY - r.top), Math.abs(anchorClientY - r.bottom));
    if (d < bestDist) { bestDist = d; idx = i; fraction = anchorClientY < r.top ? 0 : 1; }
  }
  return { idx, fraction };
}

export function Reader({ doc, onBack }: { doc: FastDoc; onBack: () => void }) {
  const [level, setLevel] = useState(0);
  const [trans, setTrans] = useState<Trans | null>(null);
  const [pulseIdx, setPulseIdx] = useState<number | null>(null);
  const [bounce, setBounce] = useState(false);
  const [dialActive, setDialActive] = useState(true);
  const [hint, setHint] = useState(() => !localStorage.getItem(`fr-hint-${doc.id}`));
  const scrollRef = useRef<HTMLDivElement>(null);
  const incomingRef = useRef<HTMLDivElement>(null);
  const idleTimer = useRef<number>(0);
  const parents = useMemo(() => deriveParents(doc), [doc]);

  const poke = useCallback(() => {
    setDialActive(true);
    window.clearTimeout(idleTimer.current);
    idleTimer.current = window.setTimeout(() => setDialActive(false), 2000);
  }, []);
  useEffect(() => { poke(); return () => window.clearTimeout(idleTimer.current); }, [poke]);

  const dismissHint = useCallback(() => {
    setHint(false);
    localStorage.setItem(`fr-hint-${doc.id}`, '1');
  }, [doc.id]);

  const requestZoom = useCallback((target: number, clientY: number | null) => {
    if (trans) return;
    if (target < 0 || target >= doc.levels.length) {
      setBounce(true);
      window.setTimeout(() => setBounce(false), 260);
      return;
    }
    if (target === level) return;
    dismissHint();
    poke();
    const container = scrollRef.current!;
    const rect = container.getBoundingClientRect();
    const anchorClientY = clientY ?? rect.top + rect.height / 2;
    const anchorY = anchorClientY - rect.top;
    const { idx, fraction } = findFocal(container, anchorClientY);
    const landing = landingIndex(doc, parents, level, target, idx, fraction);
    setTrans({
      from: level, to: target, anchorY, landingIdx: landing,
      dir: target > level ? 'in' : 'out', frozenScroll: container.scrollTop,
    });
    setLevel(target);
  }, [trans, level, doc, parents, poke, dismissHint]);

  const onStep = useCallback(
    (dir: 1 | -1, clientY: number | null) => requestZoom(level + dir, clientY),
    [requestZoom, level]);
  useZoomInput(scrollRef, onStep);

  // Position the incoming level so the landing segment sits at the anchor, then animate.
  useLayoutEffect(() => {
    if (!trans) return;
    const container = scrollRef.current!;
    const seg = container.querySelector<HTMLElement>(`[data-seg="${trans.landingIdx}"]`);
    if (seg) {
      const cRect = container.getBoundingClientRect();
      const sRect = seg.getBoundingClientRect();
      container.scrollTop = Math.max(
        0, sRect.top - cRect.top + container.scrollTop - trans.anchorY);
    }
    const inner = incomingRef.current;
    if (inner) {
      inner.style.transformOrigin = `50% ${container.scrollTop + trans.anchorY}px`;
      inner.classList.add(trans.dir === 'in' ? 'anim-in-in' : 'anim-in-out');
    }
    setPulseIdx(trans.landingIdx);
    const t1 = window.setTimeout(() => {
      inner?.classList.remove('anim-in-in', 'anim-in-out');
      setTrans(null);
    }, 320);
    const t2 = window.setTimeout(() => setPulseIdx(null), 1100);
    return () => { window.clearTimeout(t1); window.clearTimeout(t2); };
  }, [trans]);

  return (
    <div className="fixed inset-0 flex flex-col bg-[#0d0e14]" onPointerMove={poke}>
      <header className="z-10 flex items-center justify-between border-b border-[#1e2029] px-5 py-3 font-sans">
        <div className="flex items-center gap-4 min-w-0">
          <button onClick={onBack} className="text-[#6d6d7c] hover:text-[#d7d9e0] cursor-pointer">←</button>
          <span className="truncate text-[13px] tracking-[0.14em] uppercase text-[#8b8f9e]">{doc.title}</span>
        </div>
        <span className="text-[12px] text-[#b8a24a] whitespace-nowrap">
          {doc.levels[level].name} · {readingTime(doc.levels[level].words)}
        </span>
      </header>
      <div className={`relative flex-1 min-h-0 ${bounce ? 'edge-bounce' : ''}`}>
        <div ref={scrollRef}
          className={`reader-scroll h-full ${trans ? 'overflow-hidden' : 'overflow-y-auto'}`}>
          <div ref={incomingRef}>
            <LevelView segments={doc.segments[level]} kind={doc.kind} pulseIdx={pulseIdx} />
          </div>
        </div>
        {trans && (
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div style={{ transform: `translateY(-${trans.frozenScroll}px)` }}>
              <div className={trans.dir === 'in' ? 'anim-out-in' : 'anim-out-out'}
                style={{ transformOrigin: `50% ${trans.frozenScroll + trans.anchorY}px` }}>
                <LevelView segments={doc.segments[trans.from]} kind={doc.kind} />
              </div>
            </div>
          </div>
        )}
        <AltitudeDial levels={doc.levels} current={level} active={dialActive || !!trans}
          onJump={(l) => requestZoom(l, null)} onStep={(dir) => requestZoom(level + dir, null)} />
        {hint && (
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 rounded-full border
            border-[#2e2e3c] bg-[#1d1d28]/90 px-5 py-2 font-sans text-[12.5px] text-[#a5a8b5]">
            Scroll to read · hold any key while scrolling (or double-click) to dive
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Unit tests still green**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: 6 passed; no type errors.

- [ ] **Step 6: Browser-verify the full interaction set**

With both dev servers running (Task 4 Step 5), verify in the browser: plain scroll reads; ⌘/ctrl/shift/alt+scroll zooms with the paragraph under the pointer anchored; pinch zooms; double-click dives on the clicked paragraph, shift+double-click rises; `+`/`-` zoom from center; scrolling over the dial zooms; dial stop click jumps multiple levels; landing segment pulses gold; outgoing level scales toward you on dive, away on rise; gist/full-text edges bounce; hint shows once and dies on first zoom; zoom during transition is ignored. Fix regressions before committing.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat: anchored zoom with altitude-jump transition and full input scheme"
```

---

### Task 6: Attention paper content

**Files:**
- Create: `scripts/fetch_paper.py`
- Create: `data/work/paper_rewrites.json` (hand-generated at execution time)
- Create: `data/builtin/attention-is-all-you-need.json` (generated)

**Interfaces:**
- Consumes: `scripts/assemble.py` (Task 3), work-file + rewrites formats from Task 3.

- [ ] **Step 1: Fetch and parse the paper**

```bash
backend/.venv/bin/pip install beautifulsoup4 requests
```
(Dev-only tools; do not add to `backend/requirements.txt`.)

`scripts/fetch_paper.py`:
```python
"""Extract Attention Is All You Need text from arXiv's HTML rendering."""
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://arxiv.org/html/1706.03762v7"
OUT = Path("data/work/paper_sections.json")


def clean(el) -> str:
    for m in el.find_all("math"):
        alt = (m.get("alttext") or "").strip()
        m.replace_with(f" {alt} " if len(alt) <= 12 else " [equation] ")
    for c in el.find_all("cite"):
        c.replace_with("")
    return re.sub(r"\s+", " ", el.get_text()).strip()


def main():
    soup = BeautifulSoup(requests.get(URL, timeout=30).text, "html.parser")
    sections = []
    abstract = soup.find(class_="ltx_abstract")
    if abstract:
        paras = [clean(p) for p in abstract.find_all("p")]
        sections.append({"title": "Abstract", "paragraphs": [p for p in paras if p]})
    for sec in soup.find_all("section", class_="ltx_section"):
        h = sec.find(["h2", "h3"])
        title = re.sub(r"\s+", " ", h.get_text()).strip() if h else "Section"
        if re.search(r"references|acknowledg", title, re.I):
            continue
        paras = []
        for p in sec.find_all("p", class_="ltx_p"):
            t = clean(p)
            if t and len(t.split()) > 3:
                paras.append(t)
        for fig in sec.find_all("figure"):
            cap = fig.find("figcaption")
            if cap:
                cap_text = re.sub(r"\s+", " ", cap.get_text()).strip()
                paras.append(f"[{cap_text}]")
        if paras:
            sections.append({"title": title, "paragraphs": paras})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"sections": sections}, ensure_ascii=False, indent=1))
    for s in sections:
        print(f"{s['title']}: {len(s['paragraphs'])} paras, "
              f"{sum(len(p.split()) for p in s['paragraphs'])} words")
    print(f"TOTAL paras: {sum(len(s['paragraphs']) for s in sections)}")


if __name__ == "__main__":
    main()
```

Run: `backend/.venv/bin/python scripts/fetch_paper.py`
Expected: Abstract + ~7 sections with paragraph counts, total ~5–8k words. If arXiv HTML structure differs, inspect and adjust selectors (fallback mirror: `https://ar5iv.labs.arxiv.org/html/1706.03762`). Skim the output JSON — figure/equation placeholders should read as short bracketed notes, not garbage.

- [ ] **Step 2: Hand-write `data/work/paper_rewrites.json`** *(content-generation step)*

Structure (fixed):
- `id`: `attention-is-all-you-need`, `kind`: `paper`, `author`: `Vaswani et al. (2017)`
- `level_names`: `["Abstract of abstracts", "The idea", "Section by section", "Full paper"]`
- `gist`: one paragraph, 80–110 words.
- `mids[0]` "The idea": 4–6 segments, ~100–130 words each, `units` = sections covered (contiguous, sum = section count from Step 1).
- `mids[1]` "Section by section": one segment per section (in order), ~120–170 words each, `heading` = section title from Step 1 output, `units` = that section's paragraph count from Step 1 output.

Quality bar: reads as a continuous technical explanation (present tense, no "this section discusses"); accurate to the paper's actual claims and numbers (e.g. 28.4 BLEU EN-DE).

Verify: `backend/.venv/bin/python -m scripts.assemble data/work/paper_rewrites.json data/work/paper_sections.json data/builtin/attention-is-all-you-need.json` (from repo root)
Expected: `wrote … 4 levels` with rising word counts, no ValueError.

- [ ] **Step 3: Validate + verify in browser + commit**

```bash
backend/.venv/bin/python scripts/validate_data.py data/builtin/*.json
```
Expected: both files `OK`. Browser: library shows both cards; paper renders sans-serif; zoom works across its 4 levels.

```bash
git add scripts/fetch_paper.py data/work/paper_rewrites.json data/work/paper_sections.json data/builtin/attention-is-all-you-need.json
git commit -m "feat: Attention Is All You Need multi-level document"
```

---

### Task 7: Docker, Railway deploy, final walkthrough

**Files:**
- Create: `Dockerfile`, `.dockerignore`
- Modify: `README.md`

**Interfaces:**
- Consumes: everything prior. Container serves the full app on `$PORT`.

- [ ] **Step 1: Dockerfile + .dockerignore**

`Dockerfile`:
```dockerfile
FROM node:22-alpine AS fe
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY data/builtin ./data/builtin
COPY --from=fe /fe/dist ./static
ENV BUILTIN_DIR=/app/data/builtin STATIC_DIR=/app/static
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

`.dockerignore`:
```
**/node_modules
**/.venv
**/dist
.git
data/work
docs
.superpowers
```

- [ ] **Step 2: Build and smoke-test locally**

```bash
docker build -t fastreader . && docker run --rm -p 8080:8000 fastreader &
sleep 5 && curl -s localhost:8080/api/documents | head -c 200 && curl -s -o /dev/null -w " / %{http_code}\n" localhost:8080/
```
Expected: JSON with both documents; `200`. Stop the container after.

- [ ] **Step 3: Update README**

Replace `README.md` with: one-paragraph product description, screenshot placeholder-free quickstart (`uvicorn` + `npm run dev`), data pipeline commands (`fetch_alice`/`fetch_paper` → hand rewrites → `assemble` → `validate_data`), deploy note (Railway builds the Dockerfile; phase 2 needs a Volume at `DATA_DIR`).

- [ ] **Step 4: Commit, then deploy to Railway**

```bash
git add Dockerfile .dockerignore README.md
git commit -m "feat: Docker image and deploy setup"
```
Deploy with the Railway tooling available in-session (create project → deploy from the repo/Dockerfile → note the public URL). Verify `https://<railway-url>/api/documents` returns both docs.

- [ ] **Step 5: Full browser walkthrough on the deployed URL (spec §7.3)**

Drive the deployed app (orca browser): open library → Alice → every level via dial → modifier-scroll zoom at top/middle/bottom anchors → double-click dive → shift+double-click rise → `±` keys → edge bounces at gist and full text → hint appears once → paper end-to-end. Screenshot each state. Any failure: fix, redeploy, re-verify before declaring done.

- [ ] **Step 6: Final commit + push**

```bash
git status   # confirm clean
git push origin main
```
