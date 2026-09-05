# Intuitive Hole Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make end-cap hole editing feel direct while ensuring every user hole is immediately visible in the main unfolded preview and exported to DXF.

**Architecture:** Keep semantic Feature placement as the source of truth. Add one shared end-cap feature-context helper so GUI preview and DXF export resolve the same legacy/user features into unfolded coordinates. Simplify the hole editor presentation without changing stored manufacturing coordinates.

**Tech Stack:** Python 3, Tkinter, ezdxf, existing sheetmetal_features / sheetmetal_geometry modules, pytest.

## Global Constraints

- Canvas pixels are presentation only and must never be persisted as manufacturing data.
- User holes remain compatible with `head_holes` / `tail_holes` legacy dictionaries.
- Main preview and DXF must resolve the same semantic Feature objects.
- Baseline secondary features remain intact.
- No CAM compensation changes.

---

### Task 1: Shared end-cap user-feature context

**Files:**
- Modify: `sheetmetal_features.py`
- Test: `test_endcap_user_feature_preview.py`

**Interfaces:**
- Produces: `endcap_feature_context_from_geometry(geometry, finished_width, finished_depth) -> EndCapFeatureContext`

- [ ] Write failing tests proving context values come from authoritative `EndCapGeometry`.
- [ ] Run tests and confirm RED because helper does not exist.
- [ ] Implement helper with no GUI/DXF dependencies.
- [ ] Run targeted tests and confirm GREEN.

### Task 2: Main preview renders user holes

**Files:**
- Modify: `gui.py`
- Test: `test_endcap_user_feature_preview.py`

**Interfaces:**
- Consumes: legacy holes -> `legacy_hole_to_feature()` -> `resolve_endcap_features()`.
- Produces: user holes rendered in unfolded coordinates by the same resolver used for export.

- [ ] Write failing source/behavior tests proving `draw_end_cap()` consumes `head_holes` / `tail_holes` and renders resolved user features.
- [ ] Confirm RED.
- [ ] Add a small resolved-feature Canvas renderer and call it from `draw_end_cap()` after baseline/fixed features.
- [ ] Confirm targeted GREEN.

### Task 3: GUI export passes user holes

**Files:**
- Modify: `gui.py`
- Test: `test_endcap_user_feature_preview.py`

**Interfaces:**
- Head export passes `holes=self.head_holes`.
- Tail export passes `holes=self.tail_holes`.

- [ ] Write failing test/source assertion for both direct and stretched export calls.
- [ ] Confirm RED.
- [ ] Pass the appropriate hole list into both export paths.
- [ ] Confirm GREEN and DXF round-trip with one user circle and one marking pipe hole.

### Task 4: Simplify hole editor presentation

**Files:**
- Modify: `gui.py`
- Test: `test_hole_editor_ux_contract.py`

**Interfaces:**
- Default visible controls: hole type, primary size, X/Y, delete, pattern entry.
- Advanced panel: Anchor, dX/dY, pattern parameters.

- [ ] Write failing source-level UX contract test.
- [ ] Confirm RED.
- [ ] Collapse Anchor/dX/dY/pattern details behind an `進階定位 / 陣列` expander while keeping old actions available.
- [ ] Update editor guidance text to `選孔型 → 點板面 → 拖曳 → 改尺寸`.
- [ ] Confirm GREEN.

### Task 5: Full regression

**Files:**
- Test: all `test_*.py`

- [ ] Run full pytest suite.
- [ ] Run `py_compile` for six core modules.
- [ ] Produce Head/Tail DXF with user holes and read back CUTTING/MARKING entities.
- [ ] Audit GUI for persisted canvas pixel coordinates.
