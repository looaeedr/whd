# AE Engine Package Design

## Goal
Package the manufacturing core as one replaceable `ae_engine/` directory so GUI and automatic split integrations consume one authoritative implementation without merging `modules/ae.py` or duplicate sheet-metal modules.

## Architecture
`ae_engine/` owns AE geometry, feature resolution, drawing primitives, part adapters, the AE/GUI hole catalog, stable contracts, policy, cabinet-type registry, and headless manufacturing API. All imports inside the package are relative. The package keeps resource ownership outside itself: by default `config.ini` and `基準檔/` are resolved from the directory containing `ae_engine/`, while `ManufacturingContext.resource_root` remains authoritative for headless callers.

AE GUI production imports `ae_engine.ae`, `ae_engine.manufacturing_api`, and the package submodules directly. The split automatic bridges import only `ae_engine` contracts/API plus split-specific extraction modules. Legacy root/module names remain thin aliases to `ae_engine` during migration so old tests/scripts and automatic modules share the exact same class objects instead of loading duplicate Feature/Vec2 types.

## Package contents
- `ae_engine/ae.py`
- `ae_engine/contracts.py`
- `ae_engine/manufacturing_api.py`
- `ae_engine/sheetmetal_geometry.py`
- `ae_engine/sheetmetal_features.py`
- `ae_engine/sheetmetal_part_adapters.py`
- `ae_engine/sheetmetal_drawing.py`
- `ae_engine/hole_catalog.py`
- `ae_engine/cabinet_types/__init__.py`
- `ae_engine/cabinet_types/registry.py`
- `ae_engine/cabinet_types/vault.py`
- `ae_engine/cabinet_types/ro.py`
- `ae_engine/__init__.py`

## Compatibility boundary
Root AE files become module aliases to the package implementation. In the split project, only `modules/{ae,sheetmetal_*,contracts,manufacturing_api}.py` are aliases. `modules/hole_catalog.py` remains split-owned because it contains source lookup / automatic replacement behavior that is not manufacturing-core policy. They contain no manufacturing logic. This compatibility layer is temporary but safe because imports receive the same module/class identity as `ae_engine`.

## Success criteria
1. Production GUI has no direct import from legacy root AE core modules.
2. Automatic door/endcap bridges import contracts/API from `ae_engine` and still contain no `ae` dependency.
3. Compatibility imports such as `modules.sheetmetal_features.CircleFeature` are object-identical to `ae_engine.sheetmetal_features.CircleFeature`.
4. `ae_engine/` is byte-for-byte identical between AE and split deliverables.
5. Split Phase-4 package + Phase-5 update can be overlaid without touching live replacement CSV/log files.
6. Existing GUI/automatic regression and real DXF smoke remain green.


## Cabinet-type extension boundary
`ae_engine/cabinet_types/` is the stable model dispatch extension point. `金庫型` is registered as the current implemented cabinet family. `RO` / `落地盤` is registered as a known extension point but remains explicitly unimplemented at cabinet-orchestration level until its confirmed part/policy rules are supplied; Phase 5 must not invent RO geometry. Existing `generate_part()` behavior is unchanged.

The registry normalizes aliases to one canonical adapter. Future `RO.py` work may compose existing PartSpec / geometry builders or add a genuinely new topology in the geometry/part-adapter layer, but automatic split code must only pass model identity and finished-face Features.
