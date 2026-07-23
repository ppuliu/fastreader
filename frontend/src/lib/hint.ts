const KEY = 'fr-zooms';
const LEARNED_AFTER = 3;

function count(storage: Storage): number {
  const n = Number(storage.getItem(KEY));
  return Number.isFinite(n) ? n : 0;
}

/** The hint pill shows on document open until the user has zoomed a few times. */
export function shouldShowHint(storage: Storage = localStorage): boolean {
  return count(storage) < LEARNED_AFTER;
}

export function recordZoom(storage: Storage = localStorage): void {
  storage.setItem(KEY, String(count(storage) + 1));
}
