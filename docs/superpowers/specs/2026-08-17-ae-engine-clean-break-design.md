# AE Engine Clean Break Design

## Goal
Remove every transitional AE compatibility shim and leave exactly one manufacturing core: `ae_engine/`. Rename the split-project source/replacement catalog to `modules/automatic_hole_catalog.py` so there are no misleading duplicate `hole_catalog.py` names.

## Final architecture
- `ae_engine/` is the only AE/manufacturing package and the only directory copied from the AE project into the split project.
- Split production imports manufacturing geometry/features/contracts/API directly from `ae_engine`.
- `modules/automatic_hole_catalog.py` owns split-only source CSV decoding, automatic replacements, lookup, and source-name mapping.
- `modules/automatic_*` owns recognition/ownership/finished-face feature generation only.
- No `modules/ae.py`, `modules/contracts.py`, `modules/manufacturing_api.py`, or `modules/sheetmetal_*.py` remains.
- No `modules/hole_catalog.py` remains.
- AE standalone project likewise removes root compatibility files (`ae.py`, `contracts.py`, `manufacturing_api.py`, `sheetmetal_*.py`, `hole_catalog.py`); GUI/tests import `ae_engine` directly.

## Upgrade contract
Future AE upgrades replace only the `ae_engine/` directory. Split-owned `modules/automatic_hole_catalog.py`, replacement CSV, logs, config, and recognition modules are never overwritten by AE updates.

## RO extension
`ae_engine/cabinet_types/ro.py` and registry remain the extension point. RO geometry is not invented in this cleanup; package dispatch stays ready for later implementation.

## Validation
- Structural tests fail on any old core import/path or old shim file.
- All AE tests pass after root shim deletion.
- All split tests pass after import rewrite and catalog rename.
- Real Door, EndCap, direct-indicator, indicator-box and small-door DXFs read back with ezdxf.
- Overlay test proves replacing only `ae_engine/` does not alter split-owned automatic catalog or live CSV.
