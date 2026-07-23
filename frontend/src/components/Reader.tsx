import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { FastDoc } from '../lib/doc';
import { deriveParents, landingIndex, readingTime } from '../lib/doc';
import { recordZoom, shouldShowHint } from '../lib/hint';
import { LevelView } from './LevelView';
import { AltitudeDial } from './AltitudeDial';
import { useZoomInput } from '../hooks/useZoomInput';

interface Trans {
  from: number; to: number; anchorY: number; landingIdx: number;
  dir: 'in' | 'out'; frozenScroll: number;
}

interface SelPop { left: number; top: number; anchorY: number; }

function findFocal(container: HTMLElement, anchorClientY: number) {
  const segs = Array.from(container.querySelectorAll<HTMLElement>('[data-seg]'));
  let idx = 0, fraction = 0.5, bestDist = Infinity;
  for (let i = 0; i < segs.length; i++) {
    const r = segs[i].getBoundingClientRect();
    if (anchorClientY >= r.top && anchorClientY <= r.bottom) {
      return { idx: i, fraction: (anchorClientY - r.top) / Math.max(1, r.height) };
    }
    const d = Math.min(Math.abs(anchorClientY - r.top), Math.abs(anchorClientY - r.bottom));
    if (d < bestDist) { bestDist = d; idx = i; fraction = anchorClientY < r.top ? 0 : 1; }
  }
  return { idx, fraction };
}

export function Reader({ doc, onBack }: { doc: FastDoc; onBack: () => void }) {
  const [level, setLevel] = useState(0);
  const [trans, setTrans] = useState<Trans | null>(null);
  const [pulseIdx, setPulseIdx] = useState<number | null>(null);
  const [bounce, setBounce] = useState(false);
  const [hint, setHint] = useState(() => shouldShowHint());
  const [selPop, setSelPop] = useState<SelPop | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const incomingRef = useRef<HTMLDivElement>(null);
  const parents = useMemo(() => deriveParents(doc), [doc]);
  const deepest = level === doc.levels.length - 1;

  useEffect(() => {
    if (!hint) return;
    const t = window.setTimeout(() => setHint(false), 10000);
    return () => window.clearTimeout(t);
  }, [hint]);

  const requestZoom = useCallback((target: number, clientY: number | null) => {
    if (trans) return;
    if (target < 0 || target >= doc.levels.length) {
      setBounce(true);
      window.setTimeout(() => setBounce(false), 260);
      return;
    }
    if (target === level) return;
    setHint(false);
    recordZoom();
    setSelPop(null);
    window.getSelection()?.removeAllRanges();
    const container = scrollRef.current!;
    const rect = container.getBoundingClientRect();
    const anchorClientY = clientY ?? rect.top + rect.height / 2;
    const anchorY = anchorClientY - rect.top;
    const { idx, fraction } = findFocal(container, anchorClientY);
    const landing = landingIndex(doc, parents, level, target, idx, fraction);
    setTrans({
      from: level, to: target, anchorY, landingIdx: landing,
      dir: target > level ? 'in' : 'out', frozenScroll: container.scrollTop,
    });
    setLevel(target);
  }, [trans, level, doc, parents]);

  const onStep = useCallback(
    (dir: 1 | -1, clientY: number | null) => requestZoom(level + dir, clientY),
    [requestZoom, level]);
  useZoomInput(scrollRef, onStep);

  // Selection → dive popover: track the current selection while a deeper level exists.
  useEffect(() => {
    const update = () => {
      const container = scrollRef.current;
      const sel = window.getSelection();
      if (!container || !sel || sel.isCollapsed || deepest) { setSelPop(null); return; }
      const range = sel.getRangeAt(0);
      if (!container.contains(range.commonAncestorContainer)) { setSelPop(null); return; }
      const r = range.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) { setSelPop(null); return; }
      const c = container.getBoundingClientRect();
      setSelPop({
        left: Math.min(Math.max(r.left + r.width / 2 - c.left, 70), c.width - 70),
        top: Math.max(r.top - c.top - 10, 44),
        anchorY: r.top + r.height / 2,
      });
    };
    const hide = () => setSelPop(null);
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') hide(); };
    document.addEventListener('selectionchange', update);
    window.addEventListener('keydown', onKey);
    const container = scrollRef.current;
    container?.addEventListener('scroll', hide);
    return () => {
      document.removeEventListener('selectionchange', update);
      window.removeEventListener('keydown', onKey);
      container?.removeEventListener('scroll', hide);
    };
  }, [deepest]);

  // Position the incoming level so the landing segment sits at the anchor, then animate.
  useLayoutEffect(() => {
    if (!trans) return;
    const container = scrollRef.current!;
    const seg = container.querySelector<HTMLElement>(`[data-seg="${trans.landingIdx}"]`);
    if (seg) {
      const cRect = container.getBoundingClientRect();
      const sRect = seg.getBoundingClientRect();
      container.scrollTop = Math.max(
        0, sRect.top - cRect.top + container.scrollTop - trans.anchorY);
    }
    const inner = incomingRef.current;
    if (inner) {
      inner.style.transformOrigin = `50% ${container.scrollTop + trans.anchorY}px`;
      inner.classList.add(trans.dir === 'in' ? 'anim-in-in' : 'anim-in-out');
    }
    setPulseIdx(trans.landingIdx);
    const t1 = window.setTimeout(() => {
      inner?.classList.remove('anim-in-in', 'anim-in-out');
      setTrans(null);
    }, 320);
    const t2 = window.setTimeout(() => setPulseIdx(null), 1100);
    return () => { window.clearTimeout(t1); window.clearTimeout(t2); };
  }, [trans]);

  return (
    <div className="fixed inset-0 flex flex-col bg-[#0d0e14]">
      <header className="z-10 flex items-center justify-between border-b border-[#1e2029] px-5 py-3 font-sans">
        <div className="flex items-center gap-4 min-w-0">
          <button onClick={onBack} className="text-[#6d6d7c] hover:text-[#d7d9e0] cursor-pointer">←</button>
          <span className="truncate text-[13px] tracking-[0.14em] uppercase text-[#8b8f9e]">{doc.title}</span>
        </div>
        <span className="text-[12px] text-[#b8a24a] whitespace-nowrap">
          {doc.levels[level].name} · {readingTime(doc.levels[level].words)}
        </span>
      </header>
      <div className={`relative flex-1 min-h-0 ${bounce ? 'edge-bounce' : ''}`}>
        <div ref={scrollRef}
          className={`reader-scroll h-full ${trans ? 'overflow-hidden' : 'overflow-y-auto'}`}>
          <div ref={incomingRef}>
            <LevelView segments={doc.segments[level]} kind={doc.kind} pulseIdx={pulseIdx}
              onDive={deepest ? undefined : (y) => requestZoom(level + 1, y)} />
          </div>
        </div>
        {trans && (
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div style={{ transform: `translateY(-${trans.frozenScroll}px)` }}>
              <div className={trans.dir === 'in' ? 'anim-out-in' : 'anim-out-out'}
                style={{ transformOrigin: `50% ${trans.frozenScroll + trans.anchorY}px` }}>
                <LevelView segments={doc.segments[trans.from]} kind={doc.kind} />
              </div>
            </div>
          </div>
        )}
        {selPop && !trans && (
          <button
            style={{ left: selPop.left, top: selPop.top }}
            onMouseDown={(e) => { e.preventDefault(); requestZoom(level + 1, selPop.anchorY); }}
            className="absolute z-30 -translate-x-1/2 -translate-y-full whitespace-nowrap
              rounded-full border border-[#2e2e3c] bg-[#1d1d28]/95 px-4 py-1.5 font-sans
              text-[12.5px] text-[#e8dca8] shadow-[0_4px_16px_#00000066] cursor-pointer
              hover:border-[#3a3d4d]">
            ⤓ Dive deeper
          </button>
        )}
        <AltitudeDial levels={doc.levels} current={level}
          onJump={(l) => requestZoom(l, null)} onStep={(dir) => requestZoom(level + dir, null)} />
        {hint && (
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 rounded-full border
            border-[#2e2e3c] bg-[#1d1d28]/90 px-5 py-2 font-sans text-[12.5px] text-[#a5a8b5]">
            Pinch, ⌘-scroll, or double-click any paragraph to dive
          </div>
        )}
      </div>
    </div>
  );
}
