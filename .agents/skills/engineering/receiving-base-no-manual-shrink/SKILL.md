---
name: receiving-base-no-manual-shrink
description: Receiving BasePlate operator controls must not expose manual shrink values
---

# Receiving BasePlate — source only physical geometry

- Hide all four receiving-only manual shrink inputs in the live settings panel.
- The source-based physical `shrink_*` dimensions are structural, not operator-editable preferences. Never zero or discard these on save/load: EAR slots, PAD, source blank, 2D/3D and DXF rely on them.
- Do not change the common BasePlate settings for non-receiving cabinet families.
- Keep legacy project roundtrips and manufacturing validations intact; do not broaden NC authorization.
- Test actual Tk widget tree and source semantics before merging to localX. Production X only via explicit /推推.

## 2026-10-28: drawing-edge shrink and parameter panel close

- Fixing SettingsPanel fields alone leaves the four `render_base_plate_edge_controls` inputs visible around the 3D canvas. Receiving BasePlate must not construct edge controls, and `commit_base_plate_edge_shrink` must reject even direct calls; never zero true source-derived geometry.
- Unlocked part settings and assembly diagnostics must each expose an in-panel `收合參數` button wired to the same `toggle_parameter_panel`. A parameter-lock button living on the renderer canvas can become physically unreachable when unlocked panels consume vertical space.
- GUI gate: `tests/test_receiving_base_no_shrink_and_lock_reclose_gui.py`; ensure other cabinet families retain the old edge controls and neither panel gets a second boolean owner.
