import { describe, expect, it } from 'vitest';
import { recordZoom, shouldShowHint } from './hint';

function fakeStorage(): Storage {
  const map = new Map<string, string>();
  return {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
    clear: () => map.clear(),
    key: () => null,
    get length() { return map.size; },
  };
}

describe('hint', () => {
  it('shows until three zooms are recorded, then stops', () => {
    const s = fakeStorage();
    expect(shouldShowHint(s)).toBe(true);
    recordZoom(s);
    recordZoom(s);
    expect(shouldShowHint(s)).toBe(true);
    recordZoom(s);
    expect(shouldShowHint(s)).toBe(false);
  });

  it('treats garbage stored values as zero', () => {
    const s = fakeStorage();
    s.setItem('fr-zooms', 'not-a-number');
    expect(shouldShowHint(s)).toBe(true);
    recordZoom(s);
    expect(s.getItem('fr-zooms')).toBe('1');
  });
});
