import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FastDoc } from '../lib/doc';
import { deriveParents, readingTime } from '../lib/doc';
import { LevelView } from './LevelView';
import { AltitudeDial } from './AltitudeDial';

export function Reader({ doc, onBack }: { doc: FastDoc; onBack: () => void }) {
  const [level, setLevel] = useState(0);
  const [dialActive, setDialActive] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const idleTimer = useRef<number>(0);
  const parents = useMemo(() => deriveParents(doc), [doc]);
  void parents; // used by requestZoom in the anchored-zoom task

  const poke = useCallback(() => {
    setDialActive(true);
    window.clearTimeout(idleTimer.current);
    idleTimer.current = window.setTimeout(() => setDialActive(false), 2000);
  }, []);
  useEffect(() => { poke(); return () => window.clearTimeout(idleTimer.current); }, [poke]);

  const requestZoom = useCallback((target: number, clientY: number | null) => {
    void clientY; // anchoring added in the anchored-zoom task
    if (target < 0 || target >= doc.levels.length || target === level) return;
    setLevel(target);
    scrollRef.current?.scrollTo({ top: 0 });
  }, [doc, level]);

  return (
    <div className="fixed inset-0 flex flex-col bg-[#0d0e14]" onPointerMove={poke}>
      <header className="z-10 flex items-center justify-between border-b border-[#1e2029] px-5 py-3 font-sans">
        <div className="flex items-center gap-4 min-w-0">
          <button onClick={onBack} className="text-[#6d6d7c] hover:text-[#d7d9e0] cursor-pointer">←</button>
          <span className="truncate text-[13px] tracking-[0.14em] uppercase text-[#8b8f9e]">{doc.title}</span>
        </div>
        <span className="text-[12px] text-[#b8a24a] whitespace-nowrap">
          {doc.levels[level].name} · {readingTime(doc.levels[level].words)}
        </span>
      </header>
      <div className="relative flex-1 min-h-0">
        <div ref={scrollRef} className="reader-scroll h-full overflow-y-auto">
          <LevelView segments={doc.segments[level]} kind={doc.kind} />
        </div>
        <AltitudeDial levels={doc.levels} current={level} active={dialActive}
          onJump={(l) => requestZoom(l, null)} />
      </div>
    </div>
  );
}
