import type { Segment } from '../lib/doc';

export function LevelView({ segments, kind, pulseIdx, onDive }:
  { segments: Segment[]; kind: 'book' | 'paper'; pulseIdx?: number | null;
    onDive?: (clientY: number) => void }) {
  return (
    <div className={`mx-auto max-w-[68ch] px-6 pt-14 pb-[45vh] ${
      kind === 'book' ? "font-[Georgia,'Iowan_Old_Style',serif]" : 'font-sans'}`}>
      {segments.map((s, i) => (
        <div key={i} data-seg={i} className={`group relative ${pulseIdx === i ? 'seg-pulse' : ''}`}>
          {onDive && (
            <button onClick={(e) => onDive(e.clientY)} aria-label="Dive deeper here"
              className="absolute -left-10 top-1 hidden h-7 w-7 items-center justify-center
                rounded-full border border-[#2e2e3c] bg-[#1d1d28]/80 text-[13px] text-[#6d6d7c]
                opacity-0 transition-opacity duration-150 delay-150 cursor-pointer
                group-hover:opacity-100 hover:text-[#e8dca8] hover:border-[#3a3d4d] md:flex">
              ⤓
            </button>
          )}
          {s.heading && (
            <h2 className="mt-10 mb-4 text-[13px] font-sans tracking-[0.18em] uppercase text-[#8b8f9e]">
              {s.heading}
            </h2>
          )}
          <p className="mb-5 text-[17.5px] leading-[1.8]">{s.text}</p>
        </div>
      ))}
    </div>
  );
}
