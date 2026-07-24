"""FastReader processing pipeline: an Agent SDK agent (Sonnet) that rewrites a
document into aligned zoom levels, validated by the same invariants as phase 1.

The agent sees two tools: `get_source` (numbered sections/paragraphs + the level
plan) and `submit_rewrites` (assembles + validates; errors bounce back into the
loop until the document is clean)."""
import asyncio
import json
import os
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

from scripts.assemble import assemble
from scripts.chunker import chunk_text, plan_levels, word_count

SYSTEM_PROMPT = """You are FastReader's rewrite engine. You turn one document into a
pyramid of true rewrites, so a reader can zoom between depth levels like Google Maps
zooms a map.

Work strictly through your tools, in this order:
1. Read the whole document with get_source (numbered sections and paragraphs, plus
   the required level plan). Long documents come in numbered parts — call
   get_source with part=1, then part=2, and so on until the part marked
   [END OF DOCUMENT]. Never start writing before you have read every part.
2. Call submit_meta once with the level names and the gist.
3. Write each mid level top-down (coarsest first) with submit_level, in batches:
   never more than 20 segments per call. The first batch for a level uses
   append=false, every following batch for that level uses append=true. Each call
   echoes the running segment count and units sum for that level — use it to keep
   your bookkeeping straight.
4. When every level is submitted, call finalize. If it reports an error, fix the
   offending level (resubmit it with append=false, in batches) and call finalize
   again until it succeeds.

submit_level segments_json is a JSON array of segments, each:
  { "text": "...", "heading": "optional", "units": <int> }

Rules:
- Mid levels are indexed top-down: level 0 is the coarsest. Each segment's `units`
  counts how many segments of the NEXT level down it covers, consumed contiguously
  in reading order. The deepest mid's units count full-text paragraphs; they must
  sum exactly to the paragraph total, and every mid's units must sum to the segment
  count of the level below it. Choose unit boundaries at real topic/scene shifts,
  never mid-thought.
- Each level must read as ONE continuous document at that depth: flowing prose in
  present tense, faithful to exactly the span its units cover. Never write
  bullet lists, never write summarese ("this chapter discusses...", "the author
  then..."), never invent content that is not in the source.
- Aim for each level to be roughly 3-6x the word count of the level above it.
  Segment lengths within a level should be roughly even (60-170 words each).
- Where the source has named sections, put each section's title in the `heading`
  field of the segment that starts that section's coverage (at the levels where
  segments align with those sections).
- The gist is one paragraph, 70-110 words, covering the whole document.
- Level names are short (1-4 words), document-specific, and evocative - they label
  the dial stops a reader travels ("In one breath", "The argument", "Every word").
  Never generic labels like "Level 1" or "Summary".

Do not use any other tools. Do not write files."""


class RewriteAssembly:
    """Accumulates the agent's incremental submissions and assembles the document.

    Splitting the submission into per-level batches keeps every generation turn far
    below output-token limits (a whole novel's rewrites cannot fit in one tool call)
    and makes a validation error cost one level, not the whole pyramid.
    """

    def __init__(self, *, n_mids: int, work: dict, doc_meta: dict):
        self.n_mids = n_mids
        self.work = work
        self.doc_meta = doc_meta
        self.level_names: list[str] | None = None
        self.gist: str | None = None
        self.mids: list[list[dict]] = [[] for _ in range(n_mids)]

    def set_meta(self, level_names, gist) -> str | None:
        if not isinstance(level_names, list) or len(level_names) != self.n_mids + 2:
            got = len(level_names) if isinstance(level_names, list) else type(level_names).__name__
            return f"level_names must be a list of exactly {self.n_mids + 2} entries (got {got})"
        if not isinstance(gist, str) or not gist.strip():
            return "gist must be a non-empty paragraph"
        self.level_names = [str(n) for n in level_names]
        self.gist = gist.strip()
        return None

    def add_segments(self, level, segments, *, append: bool):
        """Returns (error, summary); on success error is None."""
        if not isinstance(level, int) or not 0 <= level < self.n_mids:
            return f"level must be an integer between 0 and {self.n_mids - 1}", None
        if not isinstance(segments, list) or not segments:
            return "segments_json must be a non-empty JSON array", None
        parsed = []
        for i, s in enumerate(segments):
            if (not isinstance(s, dict) or not str(s.get("text", "")).strip()
                    or not isinstance(s.get("units"), int) or s["units"] < 1):
                return (f"segment {i}: each segment needs non-empty 'text' and an "
                        f"integer 'units' >= 1", None)
            seg = {"text": str(s["text"]).strip(), "units": s["units"]}
            if s.get("heading"):
                seg["heading"] = str(s["heading"])
            parsed.append(seg)
        if append:
            self.mids[level].extend(parsed)
        else:
            self.mids[level] = parsed
        units = sum(s["units"] for s in self.mids[level])
        return None, f"level {level}: {len(self.mids[level])} segments, units sum {units}"

    def finalize(self):
        """Returns (doc, error); on success error is None."""
        if self.level_names is None:
            return None, "submit_meta has not been called yet"
        empty = [i for i, segs in enumerate(self.mids) if not segs]
        if empty:
            return None, "no segments submitted for level " + ", level ".join(map(str, empty))
        rewrites = {"level_names": self.level_names, "gist": self.gist,
                    "mids": [{"segments": segs} for segs in self.mids], **self.doc_meta}
        try:
            return assemble(rewrites, self.work), None
        except (ValueError, KeyError, TypeError) as e:
            return None, str(e)


def _status_noop(detail: str) -> None:
    pass


# One tool result must stay well under the harness's MCP output cap (~25k tokens);
# oversized results get diverted to a file the sandboxed agent cannot read.
PAGE_WORDS = 8_000


def source_pages(work: dict, page_words: int = PAGE_WORDS) -> list[str]:
    """Render the numbered sections/paragraphs as page-sized strings.

    Paragraphs are never split; a section that overflows a page continues on the
    next one with a "(cont.)" marker. Paragraph numbering is global across pages.
    """
    pages: list[list[str]] = [[]]
    budget = page_words
    p_idx = 0
    for s_idx, sec in enumerate(work["sections"]):
        heading = sec["title"] or "(untitled)"
        header = f"== SECTION {s_idx}: {heading} ({len(sec['paragraphs'])} paragraphs)"
        pages[-1].append(header)
        for para in sec["paragraphs"]:
            words = len(para.split())
            if budget - words < 0 and any(l.startswith("[") for l in pages[-1]):
                pages.append([f"== SECTION {s_idx}: {heading} (cont.)"])
                budget = page_words
            pages[-1].append(f"[{p_idx}] {para}")
            budget -= words
            p_idx += 1
        pages[-1].append("")
    return ["\n".join(lines) for lines in pages]


async def run_pipeline(raw_text: str, *, doc_id: str, title: str, author: str,
                       kind: str, out_path: str | Path, status_cb=None,
                       model: str = "claude-sonnet-5") -> dict:
    """Process raw text into a FastReader document JSON at out_path. Returns the doc."""
    status = status_cb or _status_noop
    work = chunk_text(raw_text)
    total_words = word_count(work)
    if total_words < 120:
        raise ValueError("document too short to be worth zooming (need ≥120 words)")
    n_levels = plan_levels(total_words)
    n_mids = n_levels - 2
    paragraph_total = sum(len(s["paragraphs"]) for s in work["sections"])

    state: dict = {"doc": None, "attempts": 0}
    pages = source_pages(work)
    assembly = RewriteAssembly(
        n_mids=n_mids, work=work,
        doc_meta={"id": doc_id, "title": title, "author": author, "kind": kind})

    @tool(name="get_source",
          description="Read the document: stats, required level plan, and every section/paragraph, "
                      "numbered. Large documents span multiple parts; pass `part` (1-based) and "
                      "keep reading until the final part.",
          input_schema={"part": int})
    async def get_source(args):
        part = int(args.get("part") or 1)
        if not 1 <= part <= len(pages):
            return {"content": [{"type": "text", "text":
                    f"ERROR: part must be between 1 and {len(pages)}."}]}
        status(f"agent is reading the source (part {part} of {len(pages)})")
        header = [
            f"TITLE: {title}",
            f"KIND: {kind}",
            f"TOTAL WORDS: {total_words}",
            f"PARAGRAPH TOTAL: {paragraph_total}",
            f"REQUIRED LEVELS: {n_levels} (so exactly {n_mids} mid level(s) between gist and full text)",
            f"PART {part} OF {len(pages)}"
            + ("" if part == len(pages) else f" — call get_source with part={part + 1} to continue"),
            "",
        ]
        footer = ("\n[END OF DOCUMENT]" if part == len(pages)
                  else f"\n[continued in part {part + 1} of {len(pages)}]")
        return {"content": [{"type": "text", "text": "\n".join(header) + pages[part - 1] + footer}]}

    def _text(msg: str) -> dict:
        return {"content": [{"type": "text", "text": msg}]}

    @tool(name="submit_meta",
          description="Submit the level names (JSON array of strings, top-down) and the gist "
                      "paragraph. Call once before submitting levels.",
          input_schema={"level_names_json": str, "gist": str})
    async def submit_meta(args):
        try:
            names = json.loads(args.get("level_names_json") or "null")
        except json.JSONDecodeError as e:
            return _text(f"ERROR: level_names_json is not valid JSON: {e}")
        err = assembly.set_meta(names, args.get("gist") or "")
        if err:
            return _text(f"ERROR: {err}")
        status("agent set the level plan")
        return _text(f"OK: {len(assembly.level_names)} level names and gist recorded. "
                     f"Now submit mid levels 0..{n_mids - 1} with submit_level.")

    @tool(name="submit_level",
          description="Submit a batch of segments (JSON array, max 20) for one mid level "
                      "(0 = coarsest). append=false starts the level over, append=true "
                      "extends it. Echoes the level's running segment count and units sum.",
          input_schema={"level": int, "segments_json": str, "append": bool})
    async def submit_level(args):
        try:
            segments = json.loads(args.get("segments_json") or "null")
        except json.JSONDecodeError as e:
            return _text(f"ERROR: segments_json is not valid JSON: {e}")
        err, summary = assembly.add_segments(args.get("level"), segments,
                                             append=bool(args.get("append")))
        if err:
            return _text(f"ERROR: {err}")
        status(f"agent is writing ({summary})")
        return _text(f"OK: {summary}")

    @tool(name="finalize",
          description="Assemble and validate the document from everything submitted. "
                      "Returns the error to fix, or confirms success.",
          input_schema={})
    async def finalize(args):
        state["attempts"] += 1
        status(f"validating (attempt {state['attempts']})")
        doc, err = assembly.finalize()
        if err:
            return _text(f"ERROR: {err}")
        state["doc"] = doc
        words = [lvl["words"] for lvl in doc["levels"]]
        return _text(f"SUCCESS: document assembled and validated. "
                     f"Level word counts: {words}. You are done.")

    server = create_sdk_mcp_server(name="pipeline", version="1.0.0",
                                   tools=[get_source, submit_meta, submit_level, finalize])
    tool_names = ["mcp__pipeline__get_source", "mcp__pipeline__submit_meta",
                  "mcp__pipeline__submit_level", "mcp__pipeline__finalize"]
    stderr_tail: list[str] = []

    def collect_stderr(line: str) -> None:
        stderr_tail.append(line)
        del stderr_tail[:-15]

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"pipeline": server},
        allowed_tools=tool_names,
        disallowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep",
                          "WebSearch", "WebFetch", "Task", "NotebookEdit"],
        permission_mode="bypassPermissions",
        setting_sources=[],
        max_turns=80 + 2 * len(pages),
        # The container runs as root; Claude Code only allows bypassPermissions
        # there when explicitly marked as a sandbox.
        env={"IS_SANDBOX": "1"},
        stderr=collect_stderr,
    )

    status("starting rewrite agent")
    result: ResultMessage | None = None
    try:
        async for message in query(
            prompt=f"Process the document '{title}' into {n_levels} zoom levels. "
                   f"The source has {len(pages)} part(s). Start by calling get_source "
                   f"with part=1 and read every part before writing.",
            options=options,
        ):
            if isinstance(message, ResultMessage):
                result = message
    except Exception as e:
        hint = ("" if os.environ.get("ANTHROPIC_API_KEY")
                else " — ANTHROPIC_API_KEY is not set, which this deployment requires")
        tail = f" | stderr: {' / '.join(stderr_tail[-3:])}" if stderr_tail else ""
        raise RuntimeError(f"rewrite agent failed: {e}{hint}{tail}") from e

    if state["doc"] is None:
        detail = getattr(result, "result", None) or "agent finished without a valid submission"
        if stderr_tail:
            detail = f"{detail} | stderr: {' / '.join(stderr_tail[-3:])}"
        raise RuntimeError(f"pipeline failed after {state['attempts']} attempt(s): {detail}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(state["doc"], ensure_ascii=False, indent=1))
    status("document ready")
    return state["doc"]


def run_pipeline_sync(*args, **kwargs) -> dict:
    return asyncio.run(run_pipeline(*args, **kwargs))


if __name__ == "__main__":
    import sys
    in_path, out = sys.argv[1], sys.argv[2]
    text = Path(in_path).read_text()
    doc = run_pipeline_sync(
        text, doc_id=Path(out).stem, title=Path(in_path).stem, author="Unknown",
        kind="book", out_path=out, status_cb=lambda d: print(f"  … {d}"))
    print(f"wrote {out}: {[l['words'] for l in doc['levels']]}")
