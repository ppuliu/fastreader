import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.store import DocumentStore

ROOT = Path(__file__).resolve().parents[2]
BUILTIN_DIR = os.environ.get("BUILTIN_DIR", str(ROOT / "data" / "builtin"))
DATA_DIR = os.environ.get("DATA_DIR")
STATIC_DIR = os.environ.get("STATIC_DIR", str(ROOT / "frontend" / "dist"))

store = DocumentStore(
    [BUILTIN_DIR] + ([str(Path(DATA_DIR) / "documents")] if DATA_DIR else []))

app = FastAPI(title="FastReader")


@app.get("/api/documents")
def list_documents():
    return store.list()


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    doc = store.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


if Path(STATIC_DIR).is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
