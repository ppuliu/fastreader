import type { DocSummary, FastDoc } from './lib/doc';

export interface Job {
  id: string; doc_id: string; title: string;
  status: 'queued' | 'processing' | 'done' | 'failed';
  detail: string; error: string | null; created_at: number;
}

export interface UploadPayload {
  title: string; author: string; kind: 'book' | 'paper'; text: string;
}

export async function uploadDocument(payload: UploadPayload): Promise<{ job_id: string; doc_id: string }> {
  const r = await fetch('/api/upload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const detail = (await r.json().catch(() => null))?.detail;
    throw new Error(detail || `upload failed: ${r.status}`);
  }
  return r.json();
}

export async function fetchJobs(): Promise<Job[]> {
  const r = await fetch('/api/jobs');
  if (!r.ok) throw new Error(`jobs failed: ${r.status}`);
  return r.json();
}

export async function fetchSummaries(): Promise<DocSummary[]> {
  const r = await fetch('/api/documents');
  if (!r.ok) throw new Error(`list failed: ${r.status}`);
  return r.json();
}

export async function fetchDoc(id: string): Promise<FastDoc> {
  const r = await fetch(`/api/documents/${id}`);
  if (!r.ok) throw new Error(`fetch ${id} failed: ${r.status}`);
  return r.json();
}
