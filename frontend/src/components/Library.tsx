import { useCallback, useEffect, useRef, useState } from 'react';
import type { DocSummary } from '../lib/doc';
import { readingTime } from '../lib/doc';
import type { Job } from '../api';
import { deleteJob, fetchJobs } from '../api';
import { UploadModal } from './UploadModal';

export function Library({ docs, onOpen, onRefresh }:
  { docs: DocSummary[]; onOpen: (id: string) => void; onRefresh: () => void }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [showUpload, setShowUpload] = useState(false);
  const doneSeen = useRef<Set<string>>(new Set());

  const poll = useCallback(async () => {
    try {
      const all = await fetchJobs();
      setJobs(all);
      for (const j of all) {
        if (j.status === 'done' && !doneSeen.current.has(j.id)) {
          doneSeen.current.add(j.id);
          onRefresh();
        }
      }
    } catch { /* backend briefly unavailable — keep polling */ }
  }, [onRefresh]);

  useEffect(() => { poll(); }, [poll]);
  const hasActive = jobs.some((j) => j.status === 'queued' || j.status === 'processing');
  useEffect(() => {
    if (!hasActive) return;
    const t = window.setInterval(poll, 2000);
    return () => window.clearInterval(t);
  }, [hasActive, poll]);

  const docIds = new Set(docs.map((d) => d.id));

  // A done job whose document is in the library has served its purpose — reap it.
  useEffect(() => {
    for (const j of jobs) {
      if (j.status === 'done' && docIds.has(j.doc_id)) {
        deleteJob(j.id).catch(() => {});
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs, docs]);

  const visibleJobs = jobs.filter((j) =>
    !dismissed.has(j.id) &&
    (j.status === 'queued' || j.status === 'processing' ||
     (j.status === 'failed') || (j.status === 'done' && !docIds.has(j.doc_id))));

  return (
    <div className="min-h-screen px-6 py-16 font-sans">
      <h1 className="mx-auto max-w-3xl text-3xl font-semibold tracking-tight">FastReader</h1>
      <p className="mx-auto mt-2 max-w-3xl text-[#8b8f9e]">
        Read at any altitude. Every level is a true rewrite — zoom without losing your place.
      </p>
      <div className="mx-auto mt-10 grid max-w-3xl gap-5 sm:grid-cols-2">
        {docs.map((d) => {
          const full = d.levels[d.levels.length - 1];
          return (
            <button key={d.id} onClick={() => onOpen(d.id)}
              className="rounded-xl border border-[#23232e] bg-[#12121a] p-6 text-left
                         transition-colors hover:border-[#3a3d4d] cursor-pointer">
              <div className="text-[11px] uppercase tracking-[0.16em] text-[#6d6d7c]">{d.kind}</div>
              <div className={`mt-2 text-xl text-[#e6e7ee] ${d.kind === 'book' ? "font-[Georgia,serif]" : ''}`}>
                {d.title}
              </div>
              <div className="mt-1 text-sm text-[#8b8f9e]">{d.author}</div>
              <div className="mt-4 text-[12px] text-[#b8a24a]">
                {d.levels.length} levels · {readingTime(d.levels[0].words)} → {readingTime(full.words)}
              </div>
            </button>
          );
        })}

        {visibleJobs.map((j) => (
          <div key={j.id}
            className={`rounded-xl border p-6 ${j.status === 'failed'
              ? 'border-red-900/70 bg-red-950/20' : 'border-[#2a2a36] bg-[#101018]'}`}>
            <div className="flex items-center justify-between">
              <div className="text-[11px] uppercase tracking-[0.16em] text-[#6d6d7c]">
                {j.status === 'failed' ? 'failed' : 'processing'}
              </div>
              {j.status !== 'failed' && (
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-[#d4b45a] border-t-transparent" />
              )}
            </div>
            <div className="mt-2 text-xl text-[#e6e7ee]">{j.title}</div>
            {j.status === 'failed' ? (
              <>
                <div className="mt-2 text-[12px] leading-relaxed text-red-300">{j.error || 'processing failed'}</div>
                <button
                  onClick={() => {
                    setDismissed(new Set([...dismissed, j.id]));
                    deleteJob(j.id).then(poll).catch(() => {});
                  }}
                  className="mt-3 text-[12px] text-[#8b8f9e] hover:text-[#d7d9e0] cursor-pointer">Dismiss</button>
              </>
            ) : (
              <div className="mt-2 text-[12px] text-[#8b8f9e]">{j.detail}…</div>
            )}
          </div>
        ))}

        <button onClick={() => setShowUpload(true)}
          className="flex min-h-[150px] flex-col items-center justify-center rounded-xl border
                     border-dashed border-[#2e2e3c] p-6 text-[#6d6d7c] transition-colors
                     hover:border-[#4a4d61] hover:text-[#a5a8b5] cursor-pointer">
          <span className="text-2xl">＋</span>
          <span className="mt-1 text-sm">Add a document</span>
          <span className="mt-1 text-[11px]">.txt / .md / paste text</span>
        </button>
      </div>

      {showUpload && (
        <UploadModal onClose={() => setShowUpload(false)} onStarted={poll} />
      )}
    </div>
  );
}
