from scripts.assemble import assemble
from scripts.validate_data import validate_document

WORK = {"sections": [
    {"title": "One", "paragraphs": ["p1 words here", "p2 words here"]},
    {"title": "Two", "paragraphs": ["p3 words here"]},
]}
REWRITES = {
    "id": "t", "title": "T", "author": "A", "kind": "book",
    "level_names": ["Gist", "Mid", "Full"],
    "gist": "the whole tiny thing",
    "mids": [{"segments": [
        {"text": "covers section one", "heading": "One", "units": 2},
        {"text": "covers section two", "heading": "Two", "units": 1},
    ]}],
}


def test_assemble_produces_valid_doc():
    doc = assemble(REWRITES, WORK)
    assert validate_document(doc) == []
    assert doc["levels"][0]["words"] == 4
    assert doc["segments"][2][0]["heading"] == "One"
    assert doc["segments"][2][2]["heading"] == "Two"
    assert doc["segments"][0][0]["span"] == [0, 2]
    assert doc["segments"][1][1]["span"] == [2, 3]


def test_assemble_rejects_bad_unit_totals():
    bad = {**REWRITES,
           "mids": [{"segments": [{"text": "x", "units": 1},
                                  {"text": "y", "units": 1}]}]}
    try:
        assemble(bad, WORK)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
