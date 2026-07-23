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
