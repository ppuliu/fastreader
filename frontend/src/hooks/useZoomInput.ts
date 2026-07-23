import { useEffect, type RefObject } from 'react';

/** dir: 1 = dive deeper (level+1), -1 = rise. clientY null = viewport center. */
export function useZoomInput<T extends HTMLElement>(
  containerRef: RefObject<T | null>,
  onStep: (dir: 1 | -1, clientY: number | null) => void,
) {
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let acc = 0;
    let lastWheel = 0;
    const wheel = (e: WheelEvent) => {
      if (!(e.ctrlKey || e.metaKey || e.shiftKey || e.altKey)) return; // plain scroll: untouched
      e.preventDefault();
      const now = performance.now();
      if (now - lastWheel > 250) acc = 0;
      lastWheel = now;
      acc += e.deltaY !== 0 ? e.deltaY : e.deltaX; // macOS shift+wheel arrives as deltaX
      if (Math.abs(acc) >= 60) {
        onStep(acc < 0 ? 1 : -1, e.clientY); // pinch-out / scroll-up = dive
        acc = 0;
      }
    };
    const dbl = (e: MouseEvent) => {
      e.preventDefault();
      onStep(e.shiftKey ? -1 : 1, e.clientY);
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === '+' || e.key === '=') onStep(1, null);
      else if (e.key === '-') onStep(-1, null);
    };
    el.addEventListener('wheel', wheel, { passive: false });
    el.addEventListener('dblclick', dbl);
    window.addEventListener('keydown', key);
    return () => {
      el.removeEventListener('wheel', wheel);
      el.removeEventListener('dblclick', dbl);
      window.removeEventListener('keydown', key);
    };
  }, [containerRef, onStep]);
}
