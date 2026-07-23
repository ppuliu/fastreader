import { useEffect, useRef } from 'react';
import type { LevelMeta } from '../lib/doc';

const fmtWords = (w: number) =>
  w >= 1000 ? `${(w / 1000).toFixed(w < 10000 ? 1 : 0)}k` : `${w}`;

function StepButton({ glyph, tip, disabled, onStep }:
  { glyph: string; tip: string; disabled: boolean; onStep: () => void }) {
  return (
    <button onClick={onStep} disabled={disabled}
      className={`group relative flex h-6 w-6 items-center justify-center rounded-full border
        text-[13px] leading-none transition-colors ${
        disabled
          ? 'border-[#1e2029] text-[#3a3d4d] cursor-default'
          : 'border-[#2e2e3c] bg-[#1d1d28]/80 text-[#8b8f9e] hover:text-[#e8dca8] hover:border-[#3a3d4d] cursor-pointer'}`}>
      {glyph}
      <span className="pointer-events-none absolute right-full top-1/2 mr-2.5 -translate-y-1/2
        whitespace-nowrap rounded-full border border-[#2e2e3c] bg-[#1d1d28]/95 px-3 py-1
        text-[11px] font-sans text-[#a5a8b5] opacity-0 transition-opacity duration-150
        group-hover:opacity-100">
        {tip}
      </span>
    </button>
  );
}

export function AltitudeDial({ levels, current, onJump, onStep }:
  { levels: LevelMeta[]; current: number;
    onJump: (level: number) => void; onStep: (dir: 1 | -1) => void }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const railRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    let acc = 0;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      acc += e.deltaY;
      if (Math.abs(acc) >= 60) { onStep(acc > 0 ? 1 : -1); acc = 0; } // scroll down = deeper
    };
    el.addEventListener('wheel', wheel, { passive: false });
    return () => el.removeEventListener('wheel', wheel);
  }, [onStep]);

  const dragTo = (clientY: number) => {
    const rail = railRef.current;
    if (!rail) return;
    const r = rail.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (clientY - r.top) / r.height));
    const idx = Math.round(frac * (levels.length - 1));
    if (idx !== current) onJump(idx);
  };

  return (
    <div ref={rootRef} data-dial
      className="fixed right-5 top-1/2 -translate-y-1/2 z-20 flex flex-col items-end gap-4 select-none">
      <StepButton glyph="−" tip="Rise · shift+double-click, or −"
        disabled={current === 0} onStep={() => onStep(-1)} />
      <div ref={railRef}
        onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); dragTo(e.clientY); }}
        onPointerMove={(e) => { if (e.buttons === 1) dragTo(e.clientY); }}
        className="flex flex-col items-end gap-6">
        {levels.map((l, i) => (
          <button key={i} onClick={() => onJump(i)}
            className="group flex items-center gap-2.5 cursor-pointer">
            <span className={`text-[11px] font-sans text-right transition-colors ${
              i === current ? 'text-[#e8dca8] font-semibold' : 'text-[#6d6d7c] group-hover:text-[#a5a8b5]'}`}>
              {l.name} · {fmtWords(l.words)} words
            </span>
            <span className={`rounded-full transition-all ${
              i === current
                ? 'w-3.5 h-3.5 bg-[#d4b45a] shadow-[0_0_12px_#d4b45a88]'
                : 'w-2 h-2 bg-[#3a3d4d] group-hover:bg-[#565a6e]'}`} />
          </button>
        ))}
      </div>
      <StepButton glyph="+" tip="Dive deeper · pinch, ⌘ scroll, double-click, or +"
        disabled={current === levels.length - 1} onStep={() => onStep(1)} />
    </div>
  );
}
