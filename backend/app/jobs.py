import json
import time
import uuid
from pathlib import Path


class JobStore:
    """Processing-job status as one JSON file per job (no DB, spec §5.1)."""

    def __init__(self, jobs_dir):
        self.dir = Path(jobs_dir)

    def _path(self, job_id: str) -> Path:
        return self.dir / f"{job_id}.json"

    def create(self, *, doc_id: str, title: str) -> dict:
        self.dir.mkdir(parents=True, exist_ok=True)
        job = {
            "id": uuid.uuid4().hex[:12], "doc_id": doc_id, "title": title,
            "status": "queued", "detail": "queued", "error": None,
            "created_at": time.time(),
        }
        self._path(job["id"]).write_text(json.dumps(job))
        return job

    def update(self, job_id: str, **fields) -> dict:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        job.update(fields)
        self._path(job_id).write_text(json.dumps(job))
        return job

    def get(self, job_id: str):
        path = self._path(job_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text())

    def delete(self, job_id: str) -> bool:
        path = self._path(job_id)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def list(self, limit: int = 20) -> list[dict]:
        if not self.dir.is_dir():
            return []
        jobs = [json.loads(p.read_text()) for p in self.dir.glob("*.json")]
        jobs.sort(key=lambda j: j["created_at"], reverse=True)
        return jobs[:limit]
