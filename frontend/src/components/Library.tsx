import { useState } from 'react';
import type { DocSummary } from '../lib/doc';
import { readingTime } from '../lib/doc';

function CoverThumb({ doc }: { doc: DocSummary }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return (
    <img src={`/covers/${doc.id}.jpg`} alt="" draggable={false} onError={() => setFailed(true)}
      className={`h-32 w-auto shrink-0 select-none rounded-[3px]
                  shadow-[0_6px_16px_rgba(0,0,0,0.55)]
                  ${doc.kind === 'paper' ? 'ring-1 ring-[#00000022]' : ''}`} />
  );
}

export function Library({ docs, onOpen }:
  { docs: DocSummary[]; onOpen: (id: string) => void }) {
  return (
    <div className="min-h-screen px-6 py-16 font-sans">
      <h1 className="mx-auto max-w-3xl text-3xl font-semibold tracking-tight">FastReader</h1>
      <p className="mx-auto mt-2 max-w-3xl text-[#8b8f9e]">
        Read a book the way you browse a map — zoom out for the whole story, zoom in where it gets interesting.
      </p>
      <div className="mx-auto mt-10 grid max-w-3xl gap-5 sm:grid-cols-2">
        {docs.map((d) => {
          const full = d.levels[d.levels.length - 1];
          return (
            <button key={d.id} onClick={() => onOpen(d.id)}
              className="flex items-center gap-5 rounded-xl border border-[#23232e] bg-[#12121a] p-5 text-left
                         transition-colors hover:border-[#3a3d4d] cursor-pointer">
              <CoverThumb doc={d} />
              <div className="min-w-0">
                <div className="text-[11px] uppercase tracking-[0.16em] text-[#6d6d7c]">{d.kind}</div>
                <div className={`mt-2 text-xl text-[#e6e7ee] ${d.kind === 'book' ? "font-[Georgia,serif]" : ''}`}>
                  {d.title}
                </div>
                <div className="mt-1 text-sm text-[#8b8f9e]">{d.author}</div>
                <div className="mt-4 text-[12px] text-[#b8a24a]">
                  {d.levels.length} levels · {readingTime(d.levels[0].words)} → {readingTime(full.words)}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
