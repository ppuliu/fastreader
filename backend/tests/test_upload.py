import json

import pytest
from fastapi.testclient import TestClient

from conftest import make_doc

LONG_TEXT = " ".join(f"word{i}" for i in range(200))


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    builtin = tmp_path / "builtin"
    builtin.mkdir()
    (builtin / "stub.json").write_text(json.dumps(make_doc()))
    monkeypatch.setenv("BUILTIN_DIR", str(builtin))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "uploads"))
    import importlib
    from app import main as main_mod
    importlib.reload(main_mod)
    return main_mod


@pytest.fixture()
def fake_pipeline(app_env, monkeypatch):
    """Replace the Agent SDK pipeline with a stub that writes a valid doc."""
    import scripts.pipeline as pipeline_mod

    async def fake_run(raw_text, *, doc_id, title, author, kind, out_path, status_cb=None, **kw):
        if status_cb:
            status_cb("fake processing")
        doc = make_doc(id=doc_id, title=title, author=author, kind=kind)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(doc))
        return doc

    monkeypatch.setattr(pipeline_mod, "run_pipeline", fake_run)
    return fake_run


def test_upload_processes_and_appears_in_library(app_env, fake_pipeline):
    client = TestClient(app_env.app)
    r = client.post("/api/upload", json={"title": "My Doc", "text": LONG_TEXT})
    assert r.status_code == 200, r.text
    body = r.json()
    job = client.get(f"/api/jobs/{body['job_id']}").json()
    assert job["status"] == "done"
    ids = {d["id"] for d in client.get("/api/documents").json()}
    assert body["doc_id"] in ids
    assert body["doc_id"].startswith("my-doc-")


def test_upload_rejects_short_text(app_env):
    client = TestClient(app_env.app)
    r = client.post("/api/upload", json={"title": "Tiny", "text": "too short"})
    assert r.status_code == 400


def test_upload_rejects_oversize_text(app_env):
    client = TestClient(app_env.app)
    r = client.post("/api/upload", json={"title": "Big", "text": "x" * 500_000})
    assert r.status_code == 413


def test_failed_pipeline_reports_error(app_env, monkeypatch):
    import scripts.pipeline as pipeline_mod

    async def boom(*a, **kw):
        raise RuntimeError("agent exploded")

    monkeypatch.setattr(pipeline_mod, "run_pipeline", boom)
    client = TestClient(app_env.app)
    r = client.post("/api/upload", json={"title": "Doomed", "text": LONG_TEXT})
    job = client.get(f"/api/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "failed"
    assert "agent exploded" in job["error"]


def test_jobs_listing(app_env, fake_pipeline):
    client = TestClient(app_env.app)
    client.post("/api/upload", json={"title": "One", "text": LONG_TEXT})
    client.post("/api/upload", json={"title": "Two", "text": LONG_TEXT + " extra"})
    listed = client.get("/api/jobs").json()
    assert len(listed) == 2
    assert listed[0]["title"] == "Two"  # newest first


def test_orphaned_jobs_failed_on_startup(app_env):
    job = app_env.jobs.create(doc_id="ghost", title="Ghost")
    app_env.jobs.update(job["id"], status="processing")
    with TestClient(app_env.app):  # context manager triggers startup events
        pass
    assert app_env.jobs.get(job["id"])["status"] == "failed"


def test_dismiss_deletes_failed_job(app_env, monkeypatch):
    import scripts.pipeline as pipeline_mod

    async def boom(*a, **kw):
        raise RuntimeError("nope")

    monkeypatch.setattr(pipeline_mod, "run_pipeline", boom)
    client = TestClient(app_env.app)
    r = client.post("/api/upload", json={"title": "Bad", "text": LONG_TEXT})
    job_id = r.json()["job_id"]
    assert client.delete(f"/api/jobs/{job_id}").status_code == 200
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.delete(f"/api/jobs/{job_id}").status_code == 404


def test_cannot_delete_running_job(app_env):
    job = app_env.jobs.create(doc_id="x", title="X")
    app_env.jobs.update(job["id"], status="processing")
    # plain TestClient (no context manager) so startup cleanup doesn't fail the job first
    client = TestClient(app_env.app)
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 409


def test_transcripts_served(tmp_path, monkeypatch):
    builtin = tmp_path / "builtin"
    builtin.mkdir()
    (builtin / "stub.json").write_text(json.dumps(make_doc()))
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    (tdir / "index.html").write_text("<h1>transcript</h1>")
    monkeypatch.setenv("BUILTIN_DIR", str(builtin))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("TRANSCRIPTS_DIR", str(tdir))
    import importlib
    from app import main as main_mod
    importlib.reload(main_mod)
    client = TestClient(main_mod.app)
    r = client.get("/transcripts/")
    assert r.status_code == 200
    assert "transcript" in r.text
