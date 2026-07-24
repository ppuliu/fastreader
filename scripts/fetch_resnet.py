"""Extract Deep Residual Learning (ResNet) text from ar5iv's LaTeXML rendering.

The paper predates arXiv's native HTML, so we use ar5iv, which emits the same
ltx_* markup.
"""
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://ar5iv.labs.arxiv.org/html/1512.03385"
OUT = Path("data/work/resnet_sections.json")


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
