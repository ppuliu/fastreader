import re

from scripts.pipeline import source_pages


def _work(n_sections: int, paras_per_section: int, words_per_para: int) -> dict:
    return {"sections": [
        {"title": f"Chapter {s + 1}",
         "paragraphs": [
             " ".join(f"w{s}p{p}i{i}" for i in range(words_per_para))
             for p in range(paras_per_section)
         ]}
        for s in range(n_sections)
    ]}


def _paragraph_indices(page: str) -> list[int]:
    return [int(m) for m in re.findall(r"^\[(\d+)\] ", page, flags=re.M)]


def test_small_doc_is_a_single_page():
    pages = source_pages(_work(2, 3, 50), page_words=10_000)
    assert len(pages) == 1


def test_large_doc_splits_and_covers_every_paragraph_in_order():
    work = _work(10, 20, 120)  # 24,000 words
    pages = source_pages(work, page_words=8_000)
    assert len(pages) > 1
    seen = [i for p in pages for i in _paragraph_indices(p)]
    assert seen == list(range(10 * 20))  # every paragraph once, globally numbered, in order


def test_pages_respect_word_budget():
    work = _work(10, 20, 120)
    for page in source_pages(work, page_words=8_000):
        words = sum(len(line.split()) - 1 for line in page.splitlines()
                    if line.startswith("["))
        assert words <= 8_000


def test_paragraphs_are_never_split():
    work = _work(4, 5, 400)
    pages = source_pages(work, page_words=1_000)
    para_count = {}
    for p in pages:
        for i in _paragraph_indices(p):
            para_count[i] = para_count.get(i, 0) + 1
    assert all(c == 1 for c in para_count.values())


def test_section_continuation_is_marked():
    work = _work(1, 30, 400)  # one 12,000-word section forced across pages
    pages = source_pages(work, page_words=5_000)
    assert len(pages) > 1
    assert "Chapter 1" in pages[0]
    assert any("cont." in p for p in pages[1:])
