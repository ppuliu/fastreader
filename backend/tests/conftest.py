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
