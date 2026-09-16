---
whd_doc_role: HISTORICAL
whd_contract: implementation-plan-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Issue 278 / T3 Box Body Identity / Single-Source TEST Cleanup Plan

**Goal:** Preserve the durable logical/physical box-body and single-source contracts while retiring stale test assumptions that a hidden legacy selector must be visually managed or that a logical `box_body` request must collapse to the first physical child identity.

**Exact parent:** `a6f0eaae87c4a4aa7dea8c55feaaee1dafbf21f6`

## Non-negotiable authority

- `box_body` remains the single logical top-level box-body identity.
- Receiving multipart physical children remain explicit identities: `box_body:left_side`, `box_body:back`, `box_body:right_side`.
- Structure Tree is the current visible physical-child navigation surface.
- The legacy `box_body_piece_selector` remains internal compatibility state and is not required to be geometrically managed/visible.
- Corner Data and 3D consume the same authoritative resolved render/material data.
- Caller-side structural rebuild is forbidden.
- Tests judge these contracts; tests do not define production geometry, DXF, dimensions, or identity.

## Task 1 — exact-parent RED classification

- Run the known issue76 selector-visibility node under Xvfb on the exact parent.
- Require the failure to be the stale `winfo_manager()` visibility assertion, not an environment/import failure.
- Run the known box-body logical/physical projection node on the exact parent.
- Require the failure to be logical `box_body` versus first physical `box_body:left_side` identity mismatch.
- In the same QA, prove the durable sibling contracts that should remain are GREEN.

## Task 2 — migrate stale contracts without production mutation

### `tests/test_issue76_box_body_subtabs_2d_3d.py`

- Keep one logical top-level `箱身` and no physical children as top-level menu entries.
- Replace the legacy selector geometry-manager assertion with a behavior-level assertion that physical child switching is available through the current authoritative navigation/state path.
- Keep selected physical identity and material-parity assertions.

### `tests/test_box_body_single_source_t3.py`

- Keep the no-caller-rebuild guard.
- Explicitly distinguish logical request/context from active physical child projection:
  - logical `box_body` may remain logical in the aggregate context;
  - `physical_parts` must expose the physical child identities;
  - selecting a physical child must expose that physical child context/material exactly.

### `tests/test_issue209_part_panel_projection.py`

- Preserve the current logical-presence projection contract.
- Do not turn logical projection into physical identity rewriting.

## Task 3 — GREEN acceptance

- Run all three T3 files, with Xvfb where required.
- Confirm relevant taxonomy lanes remain collected.
- Confirm no new skip/skipif/xfail controls.
- Confirm production source drift = 0.
- Confirm config.ini / DXF protected manifests are unchanged.

## Closing

- Remove temporary T3 QA workflow/scratch evidence.
- Add a permanent verification record.
- Close #278 only after exact tested-head evidence is terminal GREEN.
- Record `T3_ACCEPTED_HEAD` on Master #274 without moving the serial accepted head.
- #279 / T4 continues independently from the same T1 accepted parent.
