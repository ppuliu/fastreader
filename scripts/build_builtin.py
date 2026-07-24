"""Build a data/builtin document from a fetched sections work-file via the pipeline.

Usage:
  python -m scripts.build_builtin data/work/resnet_sections.json \
      --id deep-residual-learning --title "Deep Residual Learning for Image Recognition" \
      --author "Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun" --kind paper
"""
import argparse
import json
from pathlib import Path

from scripts.chunker import chunk_text
from scripts.pipeline import run_pipeline_sync


def sections_to_text(work: dict) -> str:
    """Render sections back to raw text with markdown headings the chunker keeps."""
    blocks = []
    for sec in work["sections"]:
        if sec.get("title"):
            blocks.append(f"## {sec['title']}")
        blocks.extend(sec["paragraphs"])
    return "\n\n".join(blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_path")
    ap.add_argument("--id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--kind", choices=["book", "paper"], required=True)
    args = ap.parse_args()

    work = json.loads(Path(args.work_path).read_text())
    text = sections_to_text(work)
    if chunk_text(text) != work:
        raise SystemExit("round-trip mismatch: a paragraph parses as a heading")

    out = Path("data/builtin") / f"{args.id}.json"
    doc = run_pipeline_sync(text, doc_id=args.id, title=args.title,
                            author=args.author, kind=args.kind, out_path=out,
                            status_cb=lambda d: print(f"  … {d}", flush=True))
    print(f"wrote {out}: {[l['words'] for l in doc['levels']]}")


if __name__ == "__main__":
    main()
