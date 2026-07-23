import type { Segment } from '../lib/doc';

export function LevelView({ segments, kind, pulseIdx }:
  { segments: Segment[]; kind: 'book' | 'paper'; pulseIdx?: number | null }) {
  return (
    <div className={`mx-auto max-w-[68ch] px-6 pt-14 pb-[45vh] ${
      kind === 'book' ? "font-[Georgia,'Iowan_Old_Style',serif]" : 'font-sans'}`}>
      {segments.map((s, i) => (
        <div key={i} data-seg={i} className={pulseIdx === i ? 'seg-pulse' : ''}>
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
