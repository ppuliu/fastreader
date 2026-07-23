import type { DocSummary, FastDoc } from './lib/doc';

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
