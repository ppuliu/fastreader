import { describe, expect, it } from 'vitest';
import { deriveParents, landingIndex, readingTime, type FastDoc } from './doc';

const doc: FastDoc = {
  id: 't', title: 'T', author: 'A', kind: 'book',
  levels: [
    { name: 'Gist', words: 4 },
    { name: 'Mid', words: 8 },
    { name: 'Full', words: 20 },
  ],
  segments: [
    [{ text: 'all', span: [0, 2] }],
    [{ text: 'a', span: [0, 2] }, { text: 'b', span: [2, 5] }],
    [{ text: 'p1' }, { text: 'p2' }, { text: 'p3' }, { text: 'p4' }, { text: 'p5' }],
  ],
};

describe('deriveParents', () => {
  it('maps children to parent indices', () => {
    const p = deriveParents(doc);
    expect(p[0]).toEqual([]);
    expect(p[1]).toEqual([0, 0]);
    expect(p[2]).toEqual([0, 0, 1, 1, 1]);
  });
});

describe('landingIndex', () => {
  const parents = deriveParents(doc);
  it('zoom in lands proportionally within children', () => {
    expect(landingIndex(doc, parents, 0, 1, 0, 0.0)).toBe(0);
    expect(landingIndex(doc, parents, 0, 1, 0, 0.6)).toBe(1);
  });
  it('zoom in clamps to last child', () => {
    expect(landingIndex(doc, parents, 1, 2, 1, 0.99)).toBe(4);
  });
  it('zoom out lands on parent', () => {
    expect(landingIndex(doc, parents, 2, 1, 3, 0.5)).toBe(1);
  });
  it('multi-level zoom dives through', () => {
    expect(landingIndex(doc, parents, 0, 2, 0, 0.5)).toBe(2);
    expect(landingIndex(doc, parents, 2, 0, 4, 0.5)).toBe(0);
  });
});

describe('readingTime', () => {
  it('formats seconds, minutes, hours', () => {
    expect(readingTime(82)).toBe('20 sec');
    expect(readingTime(1380)).toBe('~6 min');
    expect(readingTime(26400)).toBe('~1.9 hrs');
  });
});
