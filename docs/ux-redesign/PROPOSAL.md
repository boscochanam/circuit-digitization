# UI/UX redesign proposal — Wire Detection Tuner

A design study of the circuit-digitization web UI: what it is, why the current
layout fights the user, what the best comparable tools do, and a concrete,
prioritized path to a peak-desktop experience. Produced from a multi-agent
research + audit + mockup pass (5 reference-domain studies, a code-level audit,
three competing redesigns, and a synthesis). Three interactive mockups live in
`docs/ux-redesign/mockups/` — **open them in a browser** (self-contained HTML).

## What the app is for

Turn a *photo of a hand-drawn circuit* into a *simulatable SPICE netlist*:
detect components + wires -> join them into electrical nodes -> build a netlist
-> simulate. The detector leaves circuits **fragmented**, so the **core user job
is to manually connect the missing points** until the circuit is one complete,
simulatable whole. The product is, in effect, a **spatial detection-correction
tool** — closer to an image-annotation app (Roboflow / CVAT) than to a schematic
editor.

## The core problem: the primary job is buried

The audit (grounded in the code) found the whole UI is organized around
*detection tuning and inspection*, while the *actual job* is hidden. Five
high-severity issues, all verified in source:

1. **The connect editor is two levels deep.** `ConnectionEditorPanel` only mounts
   when `activeOverlay === 'topology'` (`CircuitViewport.tsx:449`), and Topology
   is filed under a generic "Analysis" group in the view bar
   (`OverlayControls.tsx:44-47`). A new user gets no signal that *this is where
   the work happens*.
2. **"Are we done?" is invisible outside that view.** The completeness signal
   ("ready to simulate" vs "incomplete — N pieces / no source") is computed
   inside the buried panel (`ConnectionEditorPanel.tsx:203-228`), so in every
   other view you cannot tell whether the circuit is simulatable.
3. **Views are a radio when they should be layers.** `handleOverlayChange`
   (`HomeClient.tsx:408-412`) makes voltage / current / topology mutually
   exclusive, so you can never see *a wrong simulation* and *the connectivity
   defect that caused it* at the same time — forcing blind toggling.
4. **"What's broken" is told three different ways.** The panel's unconnected list,
   `WarningsTab`, and `JoinCheckPanel`'s verdict use three incompatible
   definitions and never cross-link.
5. **Two join-strategy selectors disagree** and dead/duplicate chrome
   (`MetricsBar`, a redundant status bar, the abstract Topology *graph* tab that
   duplicates the spatial overlay) burn prime space.

## What the best comparable tools do

- **Image-annotation tools (Roboflow, CVAT, Label Studio)** — the closest
  analogue. Image canvas is the hero; a slim left rail holds *layer toggles* +
  the dataset *filmstrip* (with per-image status); a single right *inspector*
  swaps by selection; correction is the default mode, not a sub-view.
- **Pro/dev tools (VS Code, Chrome DevTools, Linear)** — an **activity bar** of
  modes, a **Problems panel** with "next problem" (F8), a **command palette**
  (Ctrl+K), and a **single source-of-truth status bar**. Density via hierarchy,
  not cramming.
- **EDA + node editors (KiCad ERC, Flux, n8n, Figma)** — an **ERC-style worklist**
  that gates the next step; **independent overlay layers**; selection-driven
  property inspectors; click-to-fly navigation.
- **IA principles (Refactoring UI, NN/g, Carbon/Primer)** — progressive
  disclosure, focus+context, one primary action per screen, demote the rare
  (tune-once detection knobs) behind "Advanced."

## Recommended design

An **annotation-tool "3+2" shell** as the backbone, with the best ideas from the
other two grafted in (the inline wireframe shows the layout):

- **Top status bar** — always-visible **completeness meter** ("one connected
  circuit — ready to simulate" vs "incomplete: N pieces / no source") and a
  **Simulate button gated** on completeness. The single source of truth, readable
  from anywhere. *(from the guided proposal's health meter + IDE's status bar)*
- **Left rail** — **layer toggles** (Nets, Unconnected pins, Detection, Current,
  Voltages — independent, not a radio) + a **status-coloured image filmstrip**
  so a researcher can triage which of the ~150–1680 images still need work.
  Detection-tuning sliders demoted behind "Advanced."
- **Center canvas** — the circuit photo as the hero, carrying connectivity status
  on-canvas (net colours, loose-pin rings, a proposed-merge link).
- **Right inspector** — **one** panel that swaps by selection: *Connect* (the
  searchable pin connector — the default), *Component values*, and a unified
  **Problems worklist** (one definition of "broken") that drives **click-to-fly**
  navigation and **F8 next-problem**. Replaces four components
  (`ConnectionEditorPanel` + `OverlayControls` + `ComponentPopover` + the sidebar
  sliders).
- **Bottom drawer** — netlist + warnings, collapsed by default; Raw JSON / graph /
  join-compare behind "Advanced."

The three mockups explore the same fixes through different shells — **annotation**
(recommended, 8.7), **ide** (8.2, power-user grammar), **guided** (7.4, best
onboarding). They converge on the same five fixes; pick the shell, the fixes ship
regardless.

## Roadmap

### Phase 0 — quick wins (ship incrementally in the current app, ~1 week total)
These need no shell rewrite and reuse handlers that already exist:

1. **Ungate the connect editor** (~1–2 d, highest impact) — render the connect
   editor whenever a topology result exists, independent of the raster overlay.
   Handlers (`handleReassign/Join/ConnectPins/Disconnect`,
   `HomeClient.tsx:117-193`) already exist. Fixes problem #1 alone.
2. **Promote completeness to the header** (~0.5 d) — lift the already-computed
   completeness object (`ConnectionEditorPanel.tsx:203-228`) into a persistent
   status pill, replacing the near-useless "LIVE / N imgs / preset" bar
   (`HomeClient.tsx:702-706`).
3. **Overlays radio -> independent layer toggles** (~1 d) — replace the single
   `activeOverlay` string (`CircuitViewport.tsx:115`) with a boolean map so
   defects + sim results show together. The most-cited win.
4. **Gate Simulate on completeness** (~0.5 d) — disable with "resolve all
   problems to enable" until `pieces===1 && sourceWired`.
5. **Delete dead chrome** (~0.5 d) — remove `MetricsBar` + the redundant status
   bar; move Raw JSON + the abstract Topology *graph* tab behind "Advanced."
6. **Unify the worklist + F8** (~1–2 d) — route `WarningsTab`'s signals into the
   panel's existing worklist (`ConnectionEditorPanel.tsx:435-463`); add
   click-to-pan and F8 next-problem. One definition of "broken."

### Phase 1 — structural (the shell, after quick wins de-risk it)
- Adopt the 3+2 annotation shell (refactor `HomeClient`'s `desktop-layout`).
- Build the single selection-driven inspector that retires
  `ConnectionEditorPanel` + `OverlayControls` + `ComponentPopover` + sidebar
  sliders (ends the three-surface value-edit scatter — `Sidebar.tsx:115-180`
  becomes the only value editor).
- Replace the modal `ImageGrid` with the status-coloured filmstrip navigator
  (needs a cheap per-image completeness probe, cached server-side).

### Phase 2 — power layer (last)
- Drag-from-pin spatial connect as the headline gesture (extend `findNearestPin`,
  `ConnectionEditorPanel.tsx:235-261`, into a drag interaction), panel search as
  the keyboard fallback.
- Ctrl+K command palette + single-key shortcuts (C/J/D/F8), once the shortcut set
  has settled.

## Risks / open questions
- The status-coloured filmstrip needs a fast per-image completeness probe; without
  caching it could be expensive at 1680 images.
- A single right inspector means connect-editing and value-editing aren't visible
  at once; mitigated by pinning completeness + the worklist above the swap.
- Renaming "Tuner" -> a job-focused name (the app is no longer mainly a tuner)
  is worth considering alongside the shell change.

---
*Mockups: `docs/ux-redesign/mockups/{annotation,ide,guided}.html`. This proposal is
a design study, not a committed implementation — Phase 0 items are the suggested
starting point.*
