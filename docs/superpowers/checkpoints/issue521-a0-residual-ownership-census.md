---
whd_doc_role: REFERENCE
whd_contract: issue521-a0-residual-ownership-census
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #521 / Phase 6 A0 — Fresh Residual Ownership Census + Budget Freeze

## Identity

- Master: #520
- Issue: #521
- Requirement Authority: user-approved Phase 6 v1.4
- Approved RED: R1 / R2 / R3 / R4
- Production target: `cleanup/2d-3d-sync`
- Frozen X base: `adbfa95092a35183b3b64d0d38ea8cb68be64b65`
- Work-order branch: `work/issue520-phase6-bridge-residual-reduction-20260923`
- Census branch HEAD: `2a1bdc0a1ba59f1c9c7de28a56afdbef748ecf54`
- Bridge blob: `17c4254c6aac960980c8ecfadfcd7e0ca03fc0d6`
- Bridge LOC: **7806**
- Top-level def/class: **347**
- Facade bindings: **69**
- Production behavior change: **0**

## Phase6 Knowledge Preflight

- `phase6-corner-3d-model-integrity` — GREEN
- `phase6-gui-performance-integrity` — GREEN
- global pitfall ledger — read
- Certified relief README/JSON — read
- assembly/relief pitfall ledger — read
- evidence blob: `e0946d94862af4b88afe1716ca6121e4b301ac30`

## Budget freeze

| Symbol | Value |
|---|---:|
| `PRIOR_PROTECTED_LOC` | 1194 |
| `PROTECTED_REVIEW_BUDGET` | 1314 |
| `MIN_REDUCTION` | **1000** |
| `CALCULATED_FINAL_CEILING` | 6500 |
| `EFFECTIVE_FINAL_CEILING` | **6500** |

The policy coefficients remain governance parameters, not domain/mechanical truth.

## Top-level ownership census

| classification | count |
|---|---:|
| BOUNDARY_RECONSIDERATION_CANDIDATE | 327 |
| PROTECTED_COMPATIBILITY_PRIOR | 18 |
| BRIDGE_ROOT_BOOTSTRAP | 2 |

`UNKNOWN=0`.

A0 deliberately does **not** infer DEAD/OWNER_VIOLATION from function name or LOC. Unproven residuals stay `BOUNDARY_RECONSIDERATION_CANDIDATE` until A/B evidence establishes deletion or a real owner violation.

## Residual name buckets

| bucket | symbols | span lines |
|---|---:|---:|
| other_bridge | 110 | 1899 |
| assembly_corner_relief | 57 | 1148 |
| settings | 48 | 1050 |
| project_persistence | 26 | 774 |
| derived_topology | 20 | 655 |
| legacy_fix11 | 11 | 472 |
| ui_shell | 20 | 451 |
| registry_diagnostics | 16 | 414 |
| lifecycle_update | 10 | 299 |
| workspace_navigation | 16 | 261 |
| final_scene_view | 13 | 140 |

Buckets are diagnostic navigation only; they are not ownership authority.

## Prior accepted boundary map

- #447 — **Workspace Shell**: `NO_EXTRACTION` → `PRIOR_ACCEPTED_RECONSIDERABLE_UNDER_V1_4`
- #448 — **Part Editor**: `C_KEEP_BRIDGE_COMPATIBILITY` → `PRIOR_ACCEPTED_RECONSIDERABLE_UNDER_V1_4`
- #481 — **Linked Endcap**: `KEEP_COMPATIBILITY` → `PRIOR_ACCEPTED_RECONSIDERABLE_UNDER_V1_4`
- #482 — **Settings exact-six**: `KEEP_BRIDGE_COMPATIBILITY` → `PRIOR_ACCEPTED_RECONSIDERABLE_UNDER_V1_4`
- #483 — **Dead-glue cleanup**: `PROTECTED_KEEP` → `PRIOR_ACCEPTED_RECONSIDERABLE_UNDER_V1_4`
- #502 — **Part Editor Settings commit seam**: `FIX11_LOCATION_GUARD` → `PRIOR_ACCEPTED_RECONSIDERABLE_UNDER_V1_4`

These are prior accepted decisions. Phase 6 v1.4 may supersede them only through Stage B Deletion-Test.

## Current owner map

- **Settings presentation** → `phase6_settings_panel.py::Phase6SettingsPanel`
- **Settings application sequencing** → `gui_modules/application/fold_designer_settings_coordinator.py::Phase6FoldDesignerSettingsCoordinator`
- **Settings profile pure planning** → `phase6_settings_profile_projection.py`
- **Settings transaction/service** → `phase6_settings_transaction_controller.py + phase6_settings_service.py`
- **Workspace/navigation mutation** → `phase6_workspace_navigation_controller.py + phase6_designer_workspace.py`
- **Derived-part immutable planning** → `phase6_derived_part_projection.py`
- **FinalScene composition** → `Phase6FoldDesignerComposition`
- **Diagnostics serialization** → `phase6_diagnostics.py`
- **Registry diagnostics presentation** → `phase6_registry_diagnostics_panel.py`
- **Registry diagnostics semantic/controller** → `phase6_registry_diagnostics_controller.py`
- **Fold/endcap semantics** → `phase6_fold_profiles.py + phase6_endcap_semantics.py`
- **Manufacturing/certified relief** → `ae_engine canonical manufacturing + certified registry`

## Facade inventory

- `FACADE_TOTAL=69`
- `FACADE_ACCOUNTED=69`
- `UNACCOUNTED=0`
- repo-wide consumer audit: **B6 REQUIRED**

Current compatibility posture:

| class | count |
|---|---:|
| LEGACY_REQUIRED | 16 |
| PROPERTY_COMPAT | 16 |
| PUBLIC_REQUIRED | 37 |

All 69 entries are present in the machine-readable JSON with map line, value expression, bridge raw/getattr/string evidence, public/property flags, and B6 audit marker.

This is **not** a retention verdict. B6 still has to prove `NO_CALLER / SUPERSEDED / CAN_DIRECT_OWNER / PUBLIC_REQUIRED / LEGACY_REQUIRED / PROPERTY_COMPAT` at repo-wide consumer level before deletion/retention.

## A0 hard gates

- `UNKNOWN_EQ_0=true`
- `FACADE_ACCOUNTED_EQ_TOTAL=true`
- `FACADE_COUNT_EQ_69=true`
- `PRODUCTION_BEHAVIOR_CHANGE_EQ_0=true`

## Handoff

- **A1 / #522:** only census-proven `DEAD_OR_DUPLICATE_GLUE` may be deleted. A0 currently proves none solely from static name/span evidence; A1 must add caller evidence before deletion.
- **A2 / #523:** only explicit `OWNER_VIOLATION` entries move to an existing owner. A0 currently proves none solely from static name/span evidence.
- **A3 / #524:** use the complete 69/69 facade inventory to prove direct-owner/no-caller/superseded entries.
- **A4 / #525:** compute Stage A MRG against this fixed budget; budget RED forces B-series.

## Machine-readable source

`docs/superpowers/checkpoints/issue521-a0-residual-ownership-census.json`
