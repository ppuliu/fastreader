from conftest import make_doc
from scripts.validate_data import validate_document


def test_valid_doc_passes():
    assert validate_document(make_doc()) == []


def test_level_zero_must_have_one_segment():
    doc = make_doc()
    doc["segments"][0].append({"text": "extra", "span": [0, 0]})
    assert any("level 0" in e for e in validate_document(doc))


def test_span_gap_detected():
    doc = make_doc()
    doc["segments"][1][1]["span"] = [3, 5]  # gap: 2 uncovered
    assert any("contiguous" in e for e in validate_document(doc))


def test_span_must_cover_next_level_fully():
    doc = make_doc()
    doc["segments"][1][1]["span"] = [2, 4]  # tail p5 uncovered
    assert any("cover" in e for e in validate_document(doc))


def test_last_level_must_not_have_spans():
    doc = make_doc()
    doc["segments"][2][0]["span"] = [0, 1]
    assert any("last level" in e for e in validate_document(doc))


def test_missing_span_on_mid_level():
    doc = make_doc()
    del doc["segments"][1][0]["span"]
    assert any("missing span" in e for e in validate_document(doc))


def test_levels_segments_length_mismatch():
    doc = make_doc()
    doc["levels"].pop()
    assert any("levels" in e for e in validate_document(doc))
