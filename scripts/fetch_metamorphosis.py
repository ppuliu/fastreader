"""Download The Metamorphosis from Gutenberg and parse into sections/paragraphs."""
import json
import re
import urllib.request
from pathlib import Path

URL = "https://www.gutenberg.org/cache/epub/5200/pg5200.txt"
OUT = Path("data/work/metamorphosis_sections.json")


def main():
    raw = urllib.request.urlopen(URL).read().decode("utf-8")
    raw = raw.replace("\r\n", "\n")
    body = raw.split("*** START", 1)[1].split("***", 1)[1]
    body = body.split("*** END", 1)[0]
    # Part headings are bare roman numerals on their own line: "I", "II", "III"
    parts = re.split(r"\n(I{1,3})\n", body)
    assert len(parts) == 1 + 2 * 3, f"expected 3 parts, got {(len(parts)-1)//2}"
    sections = []
    for k in range(1, len(parts), 2):
        numeral, text = parts[k], parts[k + 1]
        paras = [re.sub(r"\s+", " ", p).strip()
                 for p in re.split(r"\n\s*\n", text)]
        paras = [p for p in paras if p and set(p) - set("* ")]
        sections.append({"title": f"Part {numeral}", "paragraphs": paras})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"sections": sections}, ensure_ascii=False, indent=1))
    for s in sections:
        print(f"{s['title']}: {len(s['paragraphs'])} paras, "
              f"{sum(len(p.split()) for p in s['paragraphs'])} words")
    print(f"TOTAL paras: {sum(len(s['paragraphs']) for s in sections)}")


if __name__ == "__main__":
    main()
