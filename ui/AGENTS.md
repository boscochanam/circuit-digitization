<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Project notes (topology view / connection editor)

Context for the topology + wire-editing UI, so the non-obvious bits don't have
to be rediscovered.

## Data flow
- `HomeClient.tsx` is the orchestrator. The Topology view fetches a
  `TopologyResult` (wires / pins / components / nodes) and renders it via
  `TopologyOverlay` (the SVG over the image) plus the docked
  `ConnectionEditorPanel` (the wire-editing UI).
- Manual edits are **overrides** (`{reassign, join, remove}`) saved per image at
  `wire_detection/overrides/{dataset}/{idx}.json`. The backend bakes them into
  the netlist as node **merges** (union-find), so SPICE / voltage / current
  reflect them. Reassign/join only ever *merge* nets — they never detach from
  the old net (see the Disconnect action for removal).

## Gotcha: don't fetch nav-sensitive data via server actions
Several server actions fire at once when you navigate images (pipeline,
overrides, netlist, sim, topology). **Next serializes server actions**, and one
can be left hanging so its promise never settles — that's why the topology
overlay used to show the *previous* image until you toggled the view. Fetch
nav-sensitive data **client-side** instead (`fetch("/api/...")` — same-origin
`/api` is rewritten to the backend in `next.config.ts`) with an
`AbortController` so the latest request wins. See the topology fetch in
`HomeClient.tsx`.

## "Unconnected" means floating terminals, not floating wires
The join attaches essentially every detected wire to a net that touches a
component, so floating *wires* are ~0. The real "needs wiring" signal is a
component **pin** whose net touches no *other* component (a dead-end). Those are
ringed amber. Text-label pins are excluded — they each sit on their own isolated
node and would otherwise all read as dead-ends.

## Topology signals (what the dots / rings / colours mean)
The connection editor's **ⓘ** button opens an in-app legend. In code:
- **Net colour** — every wire/pin is coloured by its node id (`NODE_COLORS`);
  same colour = same electrical net.
- **Green / red wire-end dots** (`isEndpointConnected` in `TopologyOverlay`) —
  green if the wire's endpoint sits on a multi-component net, red if it
  dangles / dead-ends. Red is the **⚡ Quick Fix** target (auto-connect to the
  nearest good pin within 50px).
- **Amber pin rings** — a component pin whose net touches no *other* component
  (the dead-end signal above). Drawn in the pins layer, so they only show when
  Pins is on (see #40).
- The dots and the rings are two **overlapping** "needs connecting" signals at
  different granularity (wire endpoint vs component pin); keep them consistent if
  you change one, and prefer extending Quick Fix over adding a third signal.

## Datasets
`?ds=` + `?idx=` deep-link the dataset/image. The image list per dataset comes
from the backend `/api/list?ds=...`; load it for the *requested* dataset (HDC
exposes ~1680 images, gt_labels ~94).
