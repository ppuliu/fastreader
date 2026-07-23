import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Make `scripts.*` importable both locally (repo root) and in the container (/app).
_HERE = Path(__file__).resolve()
for _p in (_HERE.parents[1], _HERE.parents[2]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.store import DocumentStore  # noqa: E402
from app.jobs import JobStore  # noqa: E402

ROOT = _HERE.parents[2]
BUILTIN_DIR = os.environ.get("BUILTIN_DIR", str(ROOT / "data" / "builtin"))
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data" / "uploads")))
STATIC_DIR = os.environ.get("STATIC_DIR", str(ROOT / "frontend" / "dist"))

store = DocumentStore([BUILTIN_DIR, str(DATA_DIR / "documents")])
jobs = JobStore(DATA_DIR / "jobs")

app = FastAPI(title="FastReader")


@app.on_event("startup")
def fail_orphaned_jobs():
    """Jobs whose worker died with a previous container must not spin forever."""
    for job in jobs.list(limit=100):
        if job["status"] in ("queued", "processing"):
            jobs.update(job["id"], status="failed", detail="failed",
                        error="processing was interrupted by a server restart — please upload again")

MAX_UPLOAD_CHARS = 400_000
MIN_UPLOAD_WORDS = 120


class UploadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(default="Unknown", max_length=200)
    kind: Literal["book", "paper"] = "book"
    text: str = Field(min_length=1)


def _slug(title: str, text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "doc"
    digest = hashlib.sha1(text.encode()).hexdigest()[:6]
    return f"{base}-{digest}"


async def process_job(job_id: str, doc_id: str, req_data: dict, raw_text: str):
    from scripts.pipeline import run_pipeline  # deferred: pulls in the Agent SDK

    def status_cb(detail: str):
        jobs.update(job_id, detail=detail)

    jobs.update(job_id, status="processing", detail="starting")
    try:
        await run_pipeline(
            raw_text, doc_id=doc_id, title=req_data["title"],
            author=req_data["author"], kind=req_data["kind"],
            out_path=DATA_DIR / "documents" / f"{doc_id}.json",
            status_cb=status_cb,
        )
        jobs.update(job_id, status="done", detail="document ready")
    except Exception as e:  # surfaced to the user via the job card
        jobs.update(job_id, status="failed", detail="failed", error=str(e)[:500])


@app.get("/api/documents")
def list_documents():
    return store.list()


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    doc = store.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


@app.post("/api/upload")
def upload(req: UploadRequest, background: BackgroundTasks):
    if len(req.text) > MAX_UPLOAD_CHARS:
        raise HTTPException(status_code=413,
                            detail=f"document too large (max {MAX_UPLOAD_CHARS // 1000}k characters)")
    if len(req.text.split()) < MIN_UPLOAD_WORDS:
        raise HTTPException(status_code=400,
                            detail=f"document too short (need at least {MIN_UPLOAD_WORDS} words)")
    doc_id = _slug(req.title, req.text)
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{doc_id}.txt").write_text(req.text)
    job = jobs.create(doc_id=doc_id, title=req.title)
    background.add_task(process_job, job["id"], doc_id, req.model_dump(), req.text)
    return {"job_id": job["id"], "doc_id": doc_id}


@app.get("/api/jobs")
def list_jobs():
    return jobs.list()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


if Path(STATIC_DIR).is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
