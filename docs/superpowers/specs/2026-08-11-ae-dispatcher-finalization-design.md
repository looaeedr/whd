# AE Dispatcher Finalization Design

## Goal
Keep all existing public export functions compatible while making them thin orchestration wrappers around authoritative scene builders and one DXF save path.

## Design
- Add `_save_scene_dxf(filepath, scene)` as the only doc/layer/serialize/save path.
- Add `_build_*_scene(...)` helpers for direct Door, BoxBody, EndCap, IndicatorBox, BasePlate.
- Existing `export_*_dxf()` functions become parameter adaptation + scene builder + save.
- Add `export_part_dxf(part_type, filepath, **kwargs)` canonical dispatcher with normalized aliases.
- Stretched exporters remain scene-based and use the same `_save_scene_dxf` path.
- Do not move manufacturing geometry back into `ae.py`; builders only compose existing structural/feature/drawing results.
- Do not alter dimensions, relief formulas, layer semantics, or public function signatures.
