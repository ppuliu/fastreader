import type { LevelMeta } from '../lib/doc';
import { readingTime } from '../lib/doc';

const fmtWords = (w: number) =>
  w >= 1000 ? `${(w / 1000).toFixed(w < 10000 ? 1 : 0)}k` : `${w}`;

export function AltitudeDial({ levels, current, active, onJump }:
  { levels: LevelMeta[]; current: number; active: boolean; onJump: (level: number) => void }) {
  return (
    <div data-dial className="fixed right-5 top-1/2 -translate-y-1/2 z-20 select-none">
      {/* rail */}
      <div className={`flex flex-col items-end gap-6 transition-opacity duration-500 ${
        active ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
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
      {/* pill */}
      <div className={`absolute right-0 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-full
        border border-[#2e2e3c] bg-[#1d1d28]/80 px-4 py-1.5 text-[12px] font-sans text-[#cfc9a6]
        transition-opacity duration-500 ${active ? 'opacity-0' : 'opacity-100'}`}>
        ◈ {levels[current].name} · {readingTime(levels[current].words)}
      </div>
    </div>
  );
}
