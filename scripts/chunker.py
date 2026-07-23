"""Deterministic pre-processing for uploaded documents: text -> sections/paragraphs + level plan."""
import re

HEADING_PATTERNS = [
    re.compile(r"^#{1,4}\s+\S"),                                   # markdown heading
    re.compile(r"^(chapter|part|section|book|act)\s+([ivxlc]+|\d+)\b.{0,60}$", re.I),
    re.compile(r"^\d+(\.\d+)*[.)]?\s+[A-Z]\S{0,78}.{0,78}$"),      # "3. Model Architecture"
]


def _is_heading(line: str) -> bool:
    if len(line) > 90 or "\n" in line:
        return False
    return any(p.match(line) for p in HEADING_PATTERNS)


def _clean_heading(line: str) -> str:
    return re.sub(r"^#{1,4}\s+", "", line).strip()


def chunk_text(raw: str) -> dict:
    """Split raw text into the work-file shape: {"sections": [{title, paragraphs}]}."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    blocks = [re.sub(r"\s+", " ", b).strip() for b in re.split(r"\n\s*\n", text)]
    blocks = [b for b in blocks if b]

    sections: list[dict] = []
    current = {"title": None, "paragraphs": []}
    for block in blocks:
        if _is_heading(block):
            if current["paragraphs"]:
                sections.append(current)
            current = {"title": _clean_heading(block), "paragraphs": []}
        else:
            current["paragraphs"].append(block)
    if current["paragraphs"]:
        sections.append(current)
    if not sections:
        raise ValueError("document contains no readable paragraphs")
    return {"sections": sections}


def plan_levels(total_words: int) -> int:
    """Total level count including gist and full text (spec §3.2: each level ~3-6x the one above)."""
    if total_words < 1200:
        return 3
    if total_words < 9000:
        return 4
    if total_words < 45000:
        return 5
    return 6


def word_count(work: dict) -> int:
    return sum(len(p.split()) for s in work["sections"] for p in s["paragraphs"])
