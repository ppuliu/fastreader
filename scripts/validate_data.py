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
