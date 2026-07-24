"""The agent submits rewrites incrementally (meta, then levels in batches);
RewriteAssembly accumulates them and assembles/validates the document."""
import pytest

from scripts.chunker import chunk_text
from scripts.pipeline import RewriteAssembly

# 2 sections x 4 paragraphs, so one mid level with units summing to 8
RAW = "\n\n".join(
    part for c in (1, 2)
    for part in ([f"Chapter {c}"] + [f"chapter {c} paragraph {p} " + "word " * 30
                                     for p in range(4)])
)

META = {"id": "t", "title": "T", "author": "A", "kind": "book"}


@pytest.fixture()
def assembly():
    return RewriteAssembly(n_mids=1, work=chunk_text(RAW), doc_meta=META)


def test_meta_rejects_wrong_level_name_count(assembly):
    assert "3 entries" in assembly.set_meta(["a", "b"], "gist " * 20)
    assert assembly.set_meta(["a", "b", "c"], "gist " * 20) is None


def test_add_segments_validates_shape(assembly):
    err, _ = assembly.add_segments(0, [{"text": "ok", "units": "four"}], append=False)
    assert "units" in err
    err, _ = assembly.add_segments(5, [{"text": "ok", "units": 4}], append=False)
    assert "level" in err


def test_append_accumulates_and_replace_resets(assembly):
    _, summary = assembly.add_segments(0, [{"text": "one " * 30, "units": 4}], append=False)
    assert "units sum 4" in summary
    _, summary = assembly.add_segments(0, [{"text": "two " * 30, "units": 4}], append=True)
    assert "2 segments" in summary and "units sum 8" in summary
    _, summary = assembly.add_segments(0, [{"text": "redo " * 60, "units": 8}], append=False)
    assert "1 segments" in summary and "units sum 8" in summary


def test_finalize_reports_missing_pieces(assembly):
    doc, err = assembly.finalize()
    assert doc is None and "meta" in err
    assembly.set_meta(["a", "b", "c"], "gist " * 20)
    doc, err = assembly.finalize()
    assert doc is None and "level 0" in err


def test_finalize_assembles_valid_document(assembly):
    assembly.set_meta(["Gist", "Halves", "Every word"], "the whole story " * 8)
    assembly.add_segments(0, [{"text": "first half " * 15, "units": 4, "heading": "Chapter 1"},
                              {"text": "second half " * 15, "units": 4}], append=False)
    doc, err = assembly.finalize()
    assert err is None, err
    assert [len(level) for level in doc["segments"]] == [1, 2, 8]


def test_finalize_surfaces_unit_mismatch(assembly):
    assembly.set_meta(["Gist", "Halves", "Every word"], "the whole story " * 8)
    assembly.add_segments(0, [{"text": "only half " * 15, "units": 4}], append=False)
    doc, err = assembly.finalize()
    assert doc is None and "units sum 4" in err
