import json

import pytest
from fastapi.testclient import TestClient

from conftest import make_doc


@pytest.fixture()
def client(tmp_path, monkeypatch):
    builtin = tmp_path / "builtin"
    builtin.mkdir()
    (builtin / "stub.json").write_text(json.dumps(make_doc()))
    uploads_root = tmp_path / "uploads"
    (uploads_root / "documents").mkdir(parents=True)
    shadow = make_doc(title="Shadowed Stub")
    (uploads_root / "documents" / "stub.json").write_text(json.dumps(shadow))
    other = make_doc(id="other", title="Other")
    (uploads_root / "documents" / "other.json").write_text(json.dumps(other))
    monkeypatch.setenv("BUILTIN_DIR", str(builtin))
    monkeypatch.setenv("DATA_DIR", str(uploads_root))
    import importlib
    from app import main as main_mod
    importlib.reload(main_mod)
    return TestClient(main_mod.app)


def test_list_returns_summaries_without_segments(client):
    docs = client.get("/api/documents").json()
    ids = {d["id"] for d in docs}
    assert ids == {"stub", "other"}
    for d in docs:
        assert "segments" not in d
        assert d["levels"][0]["name"] == "Gist"


def test_data_dir_shadows_builtin(client):
    docs = {d["id"]: d for d in client.get("/api/documents").json()}
    assert docs["stub"]["title"] == "Shadowed Stub"


def test_get_returns_full_document(client):
    doc = client.get("/api/documents/stub").json()
    assert len(doc["segments"]) == 3


def test_unknown_id_404(client):
    assert client.get("/api/documents/nope").status_code == 404
