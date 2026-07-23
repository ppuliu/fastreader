export interface Segment { text: string; heading?: string; span?: [number, number]; }
export interface LevelMeta { name: string; words: number; }
export interface FastDoc {
  id: string; title: string; author: string; kind: 'book' | 'paper';
  levels: LevelMeta[]; segments: Segment[][];
}
export type DocSummary = Omit<FastDoc, 'segments'>;

export function deriveParents(doc: FastDoc): number[][] {
  const parents: number[][] = doc.segments.map(() => []);
  for (let L = 0; L < doc.segments.length - 1; L++) {
    doc.segments[L].forEach((seg, i) => {
      const [s, e] = seg.span!;
      for (let c = s; c < e; c++) parents[L + 1][c] = i;
    });
  }
  return parents;
}

export function landingIndex(
  doc: FastDoc, parents: number[][], from: number, to: number,
  focalIdx: number, fraction: number,
): number {
  let idx = focalIdx;
  let f = fraction;
  let L = from;
  while (L < to) {
    const [s, e] = doc.segments[L][idx].span!;
    const n = e - s;
    const raw = f * n;
    idx = Math.min(e - 1, s + Math.floor(raw));
    f = raw - Math.floor(raw); // carry sub-position into the next dive
    L++;
  }
  while (L > to) { idx = parents[L][idx]; L--; }
  return idx;
}

export function readingTime(words: number): string {
  const mins = words / 230;
  if (mins < 1) return `${Math.max(5, Math.round((mins * 60) / 5) * 5)} sec`;
  if (mins < 60) return `~${Math.round(mins)} min`;
  return `~${(mins / 60).toFixed(1)} hrs`;
}
