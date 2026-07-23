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
                f"(last segment '{m.get('text', '?')[:30]}…')")
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
