"""Download Alice from Gutenberg and parse into sections/paragraphs."""
import json
import re
import urllib.request
from pathlib import Path

URL = "https://www.gutenberg.org/cache/epub/11/pg11.txt"
OUT = Path("data/work/alice_sections.json")


def main():
    raw = urllib.request.urlopen(URL).read().decode("utf-8")
    raw = raw.replace("\r\n", "\n")
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
        paras = [p for p in paras
                 if p and not p.startswith("THE END") and set(p) - set("* ")]
        sections.append({"title": f"{numeral} · {title}", "paragraphs": paras})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"sections": sections}, ensure_ascii=False, indent=1))
    for s in sections:
        print(f"{s['title']}: {len(s['paragraphs'])} paras, "
              f"{sum(len(p.split()) for p in s['paragraphs'])} words")
    print(f"TOTAL paras: {sum(len(s['paragraphs']) for s in sections)}")


if __name__ == "__main__":
    main()
