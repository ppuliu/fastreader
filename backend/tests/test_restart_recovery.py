"""A deploy restarts the container mid-job; interrupted jobs must requeue, not die."""
import json
import time

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
    import scripts.pipeline as pipeline_mod

    async def fake_run(raw_text, *, doc_id, title, author, kind, out_path, status_cb=None, **kw):
        doc = make_doc(id=doc_id, title=title, author=author, kind=kind)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(doc))
        return doc

    monkeypatch.setattr(pipeline_mod, "run_pipeline", fake_run)
    return fake_run


def _orphaned_job(main_mod, *, restarts=0, with_raw=True) -> dict:
    """Simulate a job that a previous container left mid-flight."""
    job = main_mod.jobs.create(doc_id="orphan-doc-abc123", title="Orphan",
                               author="A. Author", kind="book")
    fields = {"status": "processing", "detail": "agent is writing"}
    if restarts:
        fields["restarts"] = restarts
    main_mod.jobs.update(job["id"], **fields)
    if with_raw:
        raw = main_mod.DATA_DIR / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        (raw / "orphan-doc-abc123.txt").write_text(LONG_TEXT)
    return job


def _wait_for(client, job_id, statuses, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in statuses:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job never reached {statuses}: {job}")


def test_interrupted_job_requeues_and_completes(app_env, fake_pipeline):
    job = _orphaned_job(app_env)
    with TestClient(app_env.app) as client:
        done = _wait_for(client, job["id"], {"done"})
        assert done["restarts"] == 1
        ids = {d["id"] for d in client.get("/api/documents").json()}
        assert "orphan-doc-abc123" in ids


def test_interrupted_job_fails_after_max_restarts(app_env, fake_pipeline):
    job = _orphaned_job(app_env, restarts=2)
    with TestClient(app_env.app) as client:
        failed = _wait_for(client, job["id"], {"failed"})
        assert "restart" in failed["error"]


def test_interrupted_job_without_raw_text_fails(app_env, fake_pipeline):
    job = _orphaned_job(app_env, with_raw=False)
    with TestClient(app_env.app) as client:
        failed = _wait_for(client, job["id"], {"failed"})
        assert "upload again" in failed["error"]
