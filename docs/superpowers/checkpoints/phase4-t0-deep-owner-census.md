# Phase 4 T0 — Deep-owner census

- Root baseline: `fdcc9b0a08f7ed19f5c17984f2793c16d6f49be4`
- Decision: **GREEN**
- Schema: `WHD_PHASE4_T0_CENSUS_V1`

## Canonical census

| File | Lines | self refs | unique self attrs |
|---|---:|---:|---:|
| `fold_designer_bridge.py` | 9055 | 1424 | 329 |
| `phase6_settings_transaction_controller.py` | 799 | 163 | 24 |
| `phase6_final_scene_view.py` | 1875 | 159 | 36 |
| `phase6_settings_panel.py` | 799 | 247 | 61 |
| `phase6_workspace_navigation_controller.py` | 222 | 38 | 5 |
| `phase6_project_controller.py` | 239 | 31 | 8 |
| `phase6_registry_diagnostics_controller.py` | 265 | 28 | 8 |
| `phase6_corner_data_view_adapter.py` | 262 | 4 | 1 |

## Bridge

- `_phase6_*` top-level functions: **272**
- direct class assignments: **0**
- facade bindings: **70**
- canonical bridge lines/self refs: **9055 / 1424**
- Phase 5 ownership buckets are frozen in the JSON evidence.

## Settings

- unknown self ownership: **0**
- `phase6_settings_panel.py` is classified as Tk/presentation only.
- settings-panel core reverse imports: **0**

## Final Scene

- canonical literal `self.*`: **159**
- canonical unique self attrs: **36**
- unknown self ownership: **0**

## Protected manifest

- entries: **22**
- missing: **0**
- Includes all baseline DXF files, `config.ini`, Phase 2 manufacturing owners/contracts, project persistence files, cabinet-family policy files, and Phase 3 protected/application owners.

## Gates

- `PRODUCTION_SOURCE_DRIFT=0`
- `PROTECTED_MANIFEST_MISSING=0`
- `ROOT_SHA_EXACT=1`
- `SETTINGS_PANEL_CORE_REVERSE_IMPORTS=0`
- `UNKNOWN_BRIDGE_SEAM=0`
- `UNKNOWN_FINAL_SCENE_OWNERS=0`
- `UNKNOWN_SETTINGS_OWNERS=0`

`PHASE4_T0_DECISION=GREEN`

## Acceptance provenance

- First canonical Actions run: `35461101220`
- Job: `105945001563`
- The final acceptance rerun must also prove committed JSON/Markdown exactly match regenerated evidence.
