---
whd_doc_role: REFERENCE
whd_contract: issue524-a3-facade-ratchet
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #524 / Phase 6 A3 — Narrow Delegate / Alias + Obvious Facade Ratchet

- Master: #520
- Issue: #524
- Parent accepted HEAD: `65eff72ec7a9b0b9542468454a5b4e9012d6be86`
- Facade audit RUN: `35764899441 @ e34963a8ab767322749ca3c4ab05c6bcfea43c0b` — SUCCESS
- A3 RED RUN: `35765460603 @ f7d39c7da0606d55dbc94878ef1befbff359048c` — expected RED captured
- A3 GREEN RUN: `35765706274 @ 921277d04fff38f99d38b9919a4a466551a2200f` — SUCCESS
- GREEN artifact: `10712350745`
- Facade audit artifact: `10712080995`
- RED artifact: `10711289071`

## Facade accounting

Exact tracked-tree audit:

- `FACADE_ACCOUNTED=69`
- `UNCLASSIFIED_FACADE=0`
- initial scanner classes:
  - `PUBLIC_REQUIRED=37`
  - `PROPERTY_COMPAT=16`
  - `LEGACY_REQUIRED=15`
  - apparent `NO_CALLER=1` → `__getattr__`

The apparent `__getattr__` NO_CALLER is a scanner false-negative for Python's dynamic attribute protocol. It is installed on `Phase6FoldDesignerApp` by `install_fold_designer_bridge_facade` and dispatches legacy Settings compatibility reads. Python invokes it implicitly when ordinary attribute lookup fails, so absence of an AST call site is not deletion evidence.

A3 therefore deletes **zero facade bindings**. Final facade count remains **69**.

## RED → GREEN slice

The accepted narrow-alias seam consists only of forwarding wrappers whose existing owner function has the same callable shape.

RED contract:
`tests/test_issue524_a3_facade_ratchet.py`

RED RUN `35765460603`:
- **1 failed / 2 passed**
- exact failing seam: `test_a3_direct_owner_delegates_are_identity_aliases`
- `__getattr__` retention already PASS
- facade non-growth already PASS

Production change:
- `_phase6_resolve_manufacturing_geometry = resolve_for_app`
- `_phase6_is_box_body_physical_piece_key = _dm7_is_box_body_physical_piece_key`
- `_phase6_operator_part_selector_keys = _dm7_operator_part_selector_keys`
- `_phase6_box_body_piece_keys = _dm7_box_body_piece_keys`
- `_phase6_assembly_presentation_groups = legacy_assembly_presentation_groups`

GREEN RUN `35765706274`:
- **59 passed / 0 failed**
- `FACADE_BINDING_COUNT=69`
- `DYNAMIC_GETATTR_RETAINED=1`
- `ISSUE524_A3_GREEN=GREEN`

## Quantitative effect

- bridge before: **7806 LOC**
- bridge after: **7796 LOC**
- A3 delta: **-10 LOC**
- direct identity aliases: **5**
- facade bindings removed: **0**

This small Stage-A reduction is not a completion waiver. A4 must compare the integrated Stage-A result against the frozen Appendix-A symbols. If `TOTAL_BRIDGE_REDUCTION < MIN_REDUCTION` or `FINAL_BRIDGE_LOC > EFFECTIVE_FINAL_CEILING`, `STAGE_B_REQUIRED=true` is mandatory.

## Acceptance

- [x] 69/69 facade entries accounted.
- [x] unclassified facade = 0.
- [x] dynamic `__getattr__` protocol not mis-deleted.
- [x] five behavior-identical wrappers converted to identity aliases.
- [x] facade count did not grow.
- [x] RED captured before GREEN.
- [x] focused ownership/navigation/final-scene/diagnostics regressions GREEN.
- [ ] temporary workflow cleanup.
- [ ] tested-head → closing-head production/test drift = 0.
