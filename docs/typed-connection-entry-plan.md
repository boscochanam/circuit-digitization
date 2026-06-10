# Typed Connection Entry — Plan

Tracking issue: **#44**. Status: **planned, not started.**

> **This is an *added* feature. It does not remove or replace Connect, Join, or
> Disconnect, the click-to-select flow, per-edit undo, or anything else in the
> connection editor.** It adds a second, faster way to specify a connection that
> coexists with the click flow.

---

## 1. Why

The connection editor edits wiring by **click only** today:

1. Click a wire endpoint (a white dot) to select it.
2. **Connect** it to a component pin, **Join** it to another endpoint, or
   **Disconnect** it.

The whole override model is **endpoint-centric** — every edit keys off a wire
endpoint (`reassign`, `join`, `remove` in `ConnectionOverrides`). So click can
only express what you can reach *through a visible wire endpoint*. It can't reach:

- **pin ↔ pin when there is no wire** — if the detector missed the wire entirely
  there's no endpoint to click, so the connection can't be stated at all.
- **net ↔ net** — "merge Node 3 and Node 7" is a whole-net operation; today you'd
  have to hunt for an endpoint on each.
- **dense / overlapping endpoints** — clicking the exact dot is a coin-flip.
- **by-id precision** — "put this endpoint on Node 5" instead of clicking a pin
  that happens to sit on Node 5.

## 2. Goal

Add a **typed / searchable** way to specify a connection that **complements** the
click flow. Typing and clicking feed the same form — clicking a dot on the
diagram just fills the focused field.

### Additive guarantee (explicit)

| Existing feature | After this change |
| --- | --- |
| Click endpoint → select | **Kept** |
| Connect (endpoint → pin, `reassign`) | **Kept** |
| Join (endpoint → endpoint, `join`) | **Kept** |
| Disconnect (`remove`) | **Kept** |
| Per-edit undo / Reset | **Kept** (a typed merge also gets an undo row) |
| Hover tooltips, problems list, collapse | **Kept** |

The typed form is a new section; it reuses the same override pipeline. Nothing is
removed.

## 3. Scope / non-goals

- Lives **inside the connection editor** (the docked topology panel) as its own
  section — **not** a separate floating panel, and **nothing to do** with the
  Params / Values / netlist panels.
- Does not change the simulation engine — it reuses the existing union-find merge.

## 4. UX design

A **`Connect ⟦A⟧ → ⟦B⟧`** form with two **searchable** fields:

- Type into a field → it filters a dropdown of every connectable target, each
  labelled with context:
  - wire endpoints — `wire 3 ep1 · near R2 · Node 4`
  - component pins — `R2.pin1 · Node 4`
  - whole nets — `Node 7 · R4, C3`
- **Click-fills:** clicking a dot on the diagram fills the currently-focused
  field. So click and type are one flow — pick whichever is faster.
- Pick A and B, press **Connect** → their nets merge into one node.
- Available in the **empty state** (no selection needed). When an endpoint is
  already selected, field A pre-fills with it (so the click flow flows straight
  into the form).
- Each field shows what the chosen target currently connects to, so you can see
  the effect before committing.

The form can eventually subsume Connect + Join into one control (both are just
"merge two things"), but **Phase 1 keeps the existing buttons** — see phasing.

## 5. Target catalog (what's in the dropdown)

- Wire endpoints (`wire_<idx>_ep<n>`), labelled by nearest component + node.
- Component pins (electrical only — text labels excluded; junctions TBD, see #40).
- Nets / nodes (by id + member components).
- Large lists (hundreds of pins on messy images) → cap / virtualize the dropdown,
  rank by text match.

## 6. Backend mapping

| Connection | Override | New? |
| --- | --- | --- |
| endpoint → pin | `reassign` | existing |
| endpoint → endpoint | `join` | existing |
| **pin → pin / net → net (no wire)** | **`merge: [[a, b]]`** | **new** |

The engine already does the union — `connection_overrides.apply_overrides_to_netlist`
merges nodes via union-find. The new `merge` type is a thin addition: resolve
`a`/`b` (a node id or a `component.pin` ref) to their nodes and union them. No
rewrite.

## 7. Data-model changes

- `ConnectionOverrides` (frontend `ui/src/lib/types.ts` **and** backend schema):
  add `merge?: [string, string][]` (refs like `"node:7"` or `"pin:R2.pin1"`).
- Override JSON on disk (`wire_detection/overrides/{dataset}/{idx}.json`) gains an
  optional `merge` array — older files without it still load.
- `saveOverridesAction` / load path passes `merge` through unchanged.

## 8. Phasing

- **Phase 1 — no backend change.** The searchable `A → B` form, but only for cases
  the existing overrides already support: endpoint→pin (`reassign`) and
  endpoint→endpoint (`join`). Delivers typed entry + precision + the click-fill
  flow, mapping onto today's pipeline. Fully testable on its own.
- **Phase 2 — small backend add.** The `merge` override type for the no-wire
  pin↔pin / net↔net cases. Wires through `connection_overrides.py`, the override
  route, the schema, and the frontend type.

## 9. Components touched

- `ui/src/components/ConnectionEditorPanel.tsx` — the form + searchable inputs.
- A small searchable-combobox (new component or inline) — typeahead + keyboard nav.
- `ui/src/components/CircuitViewport.tsx` — click-fills-the-focused-field wiring.
- `ui/src/app/HomeClient.tsx` — handler for the typed connect / new `merge`.
- `ui/src/lib/types.ts` — `ConnectionOverrides.merge`.
- Phase 2 backend: `wire_detection/core/connection_overrides.py`, the override
  route, the override schema.

## 10. Testing plan

- **Phase 1:** type-to-filter; pick endpoint A + pin B → `reassign` created;
  endpoint A + endpoint B → `join` created; click-fill a field; `A === B` guard;
  per-edit undo of the result; topology + SPICE reflect the merge.
- **Phase 2:** pin↔pin with no wire → `merge` override → nets merge in topology
  and SPICE; net↔net merge; undo a `merge` row.

## 11. Edge cases

- A or B not chosen → **Connect** disabled.
- A and B already on the same net → no-op / warn.
- Clicking the diagram while a field is focused → fills that field (not a normal
  endpoint selection).
- Undoing a typed merge → handled by the existing per-edit undo (a new `merge`
  row appears under "Manual edits").
- Hundreds of targets → ranked, capped dropdown.

## 12. Open questions

- Keep Connect + Join buttons alongside the form (Phase 1) and consider unifying
  later, or unify immediately? **Recommendation: keep both at first.**
- For `merge`, reference targets by **node id** or by **`component.pin`**? (Node
  id is stabler across re-runs but less intuitive; pin is intuitive but can move.)
- Junction inclusion in the pin catalog (ties to #40).

## 13. Related

- #44 (this), #39 (Connect merges but never detaches — relevant to merge
  semantics), #45 (reconcile views), #46 (per-edit undo — the undo path the merge
  rows reuse), #52 (problems-list follow-ups).
- `connection_overrides.apply_overrides_to_netlist` — the union-find merge the new
  type rides on.
