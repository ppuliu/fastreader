# Zoom Discoverability — Design

**Date:** 2026-07-23
**Scope:** Frontend only (`frontend/src`). No backend changes.

## Problem

The reader's zoom system (modifier+scroll, double-click, `+`/`-` keys, trackpad
pinch, altitude dial) is powerful but nearly invisible. After the one-shot hint
pill is dismissed, the only persistent signal is the altitude dial — and it
fades out after 2 seconds of idle, collapsing to a small pill. Nothing in the
content itself suggests paragraphs have depth beneath them. Unlike Google Maps,
text carries no cultural expectation of zoomability, so the UI must do more
work.

## Design

Four pieces that reinforce each other: an ambient "you can zoom" control, two
in-content "you can zoom *here*" affordances, and a hint that repeats until the
habit forms.

### 1. Always-visible altitude dial with +/− buttons

`AltitudeDial.tsx`, `Reader.tsx`

- The dial (level names, word counts, dots) stays at full opacity permanently.
  The idle-fade behavior and the collapsed pill are removed, along with the
  `dialActive` / `poke` idle-timer machinery in `Reader.tsx`.
- Two buttons frame the rail, spatially consistent with the altitude metaphor
  (summary = high altitude at top, detail = low at bottom):
  - **− (rise)** above the rail — tooltip: "Rise · shift+double-click, or −"
  - **+ (dive)** below the rail — tooltip: "Dive deeper · pinch, ⌘ scroll,
    double-click, or +"
- Tooltips appear on hover and double as gesture education.
- At the range edges the corresponding button dims to a disabled state
  (top level → − disabled; deepest → + disabled), passively communicating the
  range boundary.

### 2. Selection → dive popover

`Reader.tsx` (small inline component or local logic)

- On `selectionchange`/`mouseup` within the reader scroll area: if the
  selection is non-collapsed, inside the content, and a deeper level exists,
  show a floating "⤓ Dive deeper" button just above the selection rect,
  clamped to the viewport.
- Click → `requestZoom(level + 1, selectionCenterY)` — the existing anchored
  zoom centers the dive on the selected text.
- Hide on: selection collapse, scroll, Escape, zoom start.
- Never shown at the deepest level.

### 3. Hover gutter dive icon

`LevelView.tsx` (gains an `onDive(clientY)` prop), `Reader.tsx`

- Hovering a paragraph reveals a small ⤓ button in the column's left gutter,
  vertically aligned with that paragraph.
- ~150 ms appear-delay (CSS transition-delay) so it doesn't flicker while the
  mouse crosses text.
- Click dives anchored to that paragraph.
- Only rendered when a deeper level exists.

### 4. Recurring hint until the habit forms

`Reader.tsx`

- Replace the per-document `fr-hint-${doc.id}` localStorage flag with a global
  `fr-zooms` counter, incremented on every successful zoom.
- The hint pill shows on each document open while the counter is < 3,
  auto-fades after 10 s, and dismisses immediately on a zoom.
- New wording (mentions the otherwise-invisible pinch gesture):
  "Pinch, ⌘-scroll, or double-click any paragraph to dive".

## Data flow

`Reader` keeps sole ownership of `requestZoom`. New affordances are thin input
sources feeding it: dial buttons call `onStep`, the selection popover and
gutter icons pass a `clientY` anchor. No new state stores; popover/hover state
is local.

## Testing

Interaction pieces are verified in the browser. The hint counter logic
(show while < 3 zooms, increment, dismiss) is extracted into a small helper
with a vitest test alongside the existing `doc.test.ts`.
