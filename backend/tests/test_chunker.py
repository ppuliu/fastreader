import pytest

from scripts.chunker import chunk_text, plan_levels, word_count

MARKDOWN_DOC = """# Introduction

First intro paragraph with several words in it.

Second intro paragraph here.

# Methods

The methods paragraph.
"""

CHAPTER_DOC = """Chapter 1

It was a dark and stormy night in the town.

Chapter 2

The next day dawned bright and clear over everything.
"""

PLAIN_DOC = """Just one paragraph of text.

And another paragraph follows it.
"""


def test_markdown_headings_become_sections():
    work = chunk_text(MARKDOWN_DOC)
    assert [s["title"] for s in work["sections"]] == ["Introduction", "Methods"]
    assert len(work["sections"][0]["paragraphs"]) == 2
    assert len(work["sections"][1]["paragraphs"]) == 1


def test_chapter_headings_detected():
    work = chunk_text(CHAPTER_DOC)
    assert [s["title"] for s in work["sections"]] == ["Chapter 1", "Chapter 2"]


def test_plain_text_single_untitled_section():
    work = chunk_text(PLAIN_DOC)
    assert len(work["sections"]) == 1
    assert work["sections"][0]["title"] is None
    assert len(work["sections"][0]["paragraphs"]) == 2


def test_empty_document_rejected():
    with pytest.raises(ValueError):
        chunk_text("   \n\n  ")


def test_plan_levels_scales_with_size():
    assert plan_levels(500) == 3
    assert plan_levels(5000) == 4
    assert plan_levels(26000) == 5
    assert plan_levels(120000) == 6


def test_word_count():
    assert word_count(chunk_text(PLAIN_DOC)) == 10
