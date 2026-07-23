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
    AssistantMessage,
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

Work strictly through your two tools:
1. Call get_source once to read the document (numbered sections and paragraphs) and
   the required level plan.
2. Write the rewrites and call submit_rewrites. If it returns errors, fix them and
   submit again until it succeeds.

The rewrites JSON you submit has exactly this shape:
{
  "level_names": [<n_mids + 2 short names, top-down: gist level first, full-text level last>],
  "gist": "<one paragraph, 70-110 words, the whole document>",
  "mids": [ { "segments": [ { "text": "...", "heading": "optional", "units": <int> } ] }, ... ]
}

Rules:
- mids are ordered top-down (coarsest first). Each segment's `units` counts how many
  segments of the NEXT level down it covers, consumed contiguously in reading order.
  The deepest mid's units count full-text paragraphs; they must sum exactly to the
  paragraph total, and every mid's units must sum to the segment count of the level
  below it. Choose unit boundaries at real topic/scene shifts, never mid-thought.
- Each level must read as ONE continuous document at that depth: flowing prose in
  present tense, faithful to exactly the span its units cover. Never write
  bullet lists, never write summarese ("this chapter discusses...", "the author
  then..."), never invent content that is not in the source.
- Aim for each level to be roughly 3-6x the word count of the level above it.
  Segment lengths within a level should be roughly even (60-170 words each).
- Where the source has named sections, put each section's title in the `heading`
  field of the segment that starts that section's coverage (at the levels where
  segments align with those sections).
- Level names are short (1-4 words), document-specific, and evocative - they label
  the dial stops a reader travels ("In one breath", "The argument", "Every word").
  Never generic labels like "Level 1" or "Summary".

Do not use any other tools. Do not write files. Work in this order: get_source,
think through the structure, then submit."""


def _status_noop(detail: str) -> None:
    pass


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

    @tool(name="get_source",
          description="Read the document: stats, required level plan, and every section/paragraph, numbered.",
          input_schema={})
    async def get_source(args):
        status("agent is reading the source")
        lines = [
            f"TITLE: {title}",
            f"KIND: {kind}",
            f"TOTAL WORDS: {total_words}",
            f"PARAGRAPH TOTAL: {paragraph_total}",
            f"REQUIRED LEVELS: {n_levels} (so exactly {n_mids} mid level(s) between gist and full text)",
            "",
        ]
        p_idx = 0
        for s_idx, sec in enumerate(work["sections"]):
            heading = sec["title"] or "(untitled)"
            lines.append(f"== SECTION {s_idx}: {heading} ({len(sec['paragraphs'])} paragraphs)")
            for para in sec["paragraphs"]:
                lines.append(f"[{p_idx}] {para}")
                p_idx += 1
            lines.append("")
        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    @tool(name="submit_rewrites",
          description="Submit the rewrites JSON (as a string). Assembles and validates the "
                      "document; returns errors to fix, or confirms success.",
          input_schema={"rewrites_json": str})
    async def submit_rewrites(args):
        state["attempts"] += 1
        status(f"validating rewrite attempt {state['attempts']}")
        try:
            rewrites = json.loads(args["rewrites_json"])
        except json.JSONDecodeError as e:
            return {"content": [{"type": "text", "text": f"ERROR: rewrites_json is not valid JSON: {e}"}]}
        rewrites.update({"id": doc_id, "title": title, "author": author, "kind": kind})
        names = rewrites.get("level_names") or []
        if len(names) != n_mids + 2:
            return {"content": [{"type": "text", "text":
                    f"ERROR: level_names must have exactly {n_mids + 2} entries (got {len(names)})."}]}
        if len(rewrites.get("mids") or []) != n_mids:
            return {"content": [{"type": "text", "text":
                    f"ERROR: mids must have exactly {n_mids} level(s) (got {len(rewrites.get('mids') or [])})."}]}
        try:
            doc = assemble(rewrites, work)
        except (ValueError, KeyError, TypeError) as e:
            return {"content": [{"type": "text", "text": f"ERROR: {e}"}]}
        state["doc"] = doc
        words = [lvl["words"] for lvl in doc["levels"]]
        return {"content": [{"type": "text", "text":
                f"SUCCESS: document assembled and validated. Level word counts: {words}. You are done."}]}

    server = create_sdk_mcp_server(name="pipeline", version="1.0.0",
                                   tools=[get_source, submit_rewrites])
    tool_names = ["mcp__pipeline__get_source", "mcp__pipeline__submit_rewrites"]
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
        max_turns=30,
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
                   f"Start by calling get_source.",
            options=options,
        ):
            if isinstance(message, AssistantMessage):
                status(f"agent is writing (attempt {state['attempts'] + 1} of the rewrite)")
            elif isinstance(message, ResultMessage):
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
