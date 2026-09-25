---
whd_doc_role: REFERENCE
whd_contract: issue291-t3-selector-plan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #291 T3 Selector / Navigation / Subtab Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the approved T3 selector/navigation/subtab presentation from `gui.py` into focused `gui_modules/parts` helpers while preserving authoritative physical-part identity and behavior.

**Architecture:** Keep `Phase6WorkspaceController` and the existing host as state/geometry owners. New parts modules receive the host as a routing/presentation dependency, may retain only transient Tk widget maps/guards, and never introduce committed current-part/presence state. `gui.py` keeps compatibility method names as thin delegates and delegates the physical box-body subtab builder.

**Tech Stack:** Python 3, tkinter/ttk, pytest, GitHub Actions/Xvfb.

**Spec:** `docs/superpowers/specs/2026-09-16-issue291-t3-selector-design.md`

## Global Constraints

- Accepted predecessor remains `#290 @ f11ab72850d893f5935ad869ab8ae9205fc0cd92`.
- Work stays on `refactor/issue291-gui-phase2-t3-selector-20260916`; production `cleanup/2d-3d-sync` is not updated by T3.
- `gui.py <= 8,520` lines after the legal T3 extraction.
- New modules must not import root `gui` or `compatibility.legacy_exports`.
- No second `active_part`, `current_part`, `existing_parts`, or `part_presence` authority.
- Stable physical IDs `box_body:left_side`, `box_body:back`, `box_body:right_side` remain unchanged.
- Callbacks remain Event Unpacking -> Normalize -> Route / Dispatch.
- `_phase6_set_part_presence` stays in the host/controller seam.
- Do not move T4 panels/state, T5 editors, manufacturing/DXF/project-schema authority, or T7 controller boundaries.
- Protected files/semantics (`config.ini`, `基準檔/**`, `ae_engine/**`, `phase6_project_file.py`, `phase6_fold_profiles.py`) must remain unchanged.

---

### Task 1: Focused presence presentation module

**Files:**
- Create: `gui_modules/parts/__init__.py`
- Create: `gui_modules/parts/selector.py`
- Test: `tests/test_issue291_gui_phase2_t3_selector.py`

**Interfaces:**
- Consumes: host methods/attributes `_phase6_current_existing_parts`, `_phase6_logical_part_present`, result/output Tk widgets and result variables.
- Produces: `refresh_presence_ui(host, supplied_parts=None) -> set[str]`.

- [ ] **Step 1: Re-run the existing RED contract**

Run: `pytest -q tests/test_issue291_gui_phase2_t3_selector.py`
Expected: RED because `gui_modules/parts` does not exist and root methods are still inline.

- [ ] **Step 2: Add the stateless presentation helper**

```python
# gui_modules/parts/selector.py
import tkinter as tk


def refresh_presence_ui(host, supplied_parts=None):
    present = set(supplied_parts) if supplied_parts is not None else host._phase6_current_existing_parts()
    present.add("box_body")
    result_groups = getattr(host, "_phase6_result_part_rows", {}) or {}
    visibility = {
        "box_body": host._phase6_logical_part_present(present, "box_body"),
        "endcap": bool({"head", "tail"} & present),
        "door": host._phase6_logical_part_present(present, "door"),
        "base_plate": host._phase6_logical_part_present(present, "base_plate"),
        "indicator_box": "indicator_box" in present,
        "indicator_door": "indicator_door" in present,
    }
    for group in ("box_body", "endcap", "door", "base_plate", "indicator_box", "indicator_door"):
        for row in result_groups.get(group, ()):
            row.pack_forget()
            if visibility[group]:
                row.pack(fill=tk.X, pady=6, padx=10)
    output_widgets = getattr(host, "_phase6_output_part_widgets", {}) or {}
    output_order = ("box_body", "head", "tail", "door", "base_plate", "indicator_box", "indicator_door")
    for widget in output_widgets.values():
        widget.pack_forget()
    visible_keys = [key for key in output_order if host._phase6_logical_part_present(present, key) and key in output_widgets]
    for index, key in enumerate(visible_keys):
        pady = (6, 1) if index == 0 else ((1, 6) if index == len(visible_keys) - 1 else (1, 1))
        output_widgets[key].pack(anchor=tk.W, padx=10, pady=pady)
    if not visibility["endcap"]:
        host.result_y_w_var.set("-"); host.result_y_d_var.set("-")
    if not visibility["door"]:
        host.result_door_w_var.set("-"); host.result_door_h_var.set("-")
    if not visibility["base_plate"]:
        host.result_base_plate_w_var.set("-"); host.result_base_plate_h_var.set("-")
    if not visibility["indicator_box"]:
        host.result_ib_w_var.set("-"); host.result_ib_h_var.set("-")
    if not visibility["indicator_door"]:
        host.result_ib_door_w_var.set("-"); host.result_ib_door_h_var.set("-")
    return present
```

- [ ] **Step 3: Verify focused ownership constraints**

Run: `pytest -q tests/test_issue291_gui_phase2_t3_selector.py::test_t3_parts_modules_do_not_import_root_or_legacy_compatibility tests/test_issue291_gui_phase2_t3_selector.py::test_t3_modules_do_not_create_second_authoritative_part_or_presence_store`
Expected: the ownership/import checks are GREEN once the package exists; structural delegation checks remain RED until Task 2.

### Task 2: Physical box-body subtab module and host delegates

**Files:**
- Create: `gui_modules/parts/subtabs.py`
- Modify: `gui.py`
- Test: `tests/test_issue291_gui_phase2_t3_selector.py`

**Interfaces:**
- Consumes: host Tk root, `box_body_piece_2d_selected_var`, `box_body_face_selected_var`, `box_body_canvas_frame`, `draw_preview`, `open_box_body_face_editor`.
- Produces: `build_box_body_piece_selector(host, parent)`, `box_body_piece_label(part_key)`, `box_body_piece_face_key(part_key)`, `refresh_box_body_piece_tabs_2d(host, render_data)`, `on_box_body_piece_2d_tab_changed(host, event=None)`, `on_box_body_piece_double_click(host, event=None)`.

- [ ] **Step 1: Add the focused subtab implementation by moving the existing behavior unchanged**

`subtabs.py` imports only `tkinter as tk` and `from tkinter import ttk`. It owns no committed physical state; `_box_body_piece_2d_tab_map`, `_box_body_piece_2d_tab_keys`, and `_box_body_piece_2d_tab_guard` remain transient widget routing state on the host.

- [ ] **Step 2: Replace root behavior with thin delegates**

Add imports:

```python
from gui_modules.parts.selector import refresh_presence_ui as _refresh_presence_ui_impl
from gui_modules.parts.subtabs import (
    build_box_body_piece_selector,
    box_body_piece_label as _box_body_piece_label_impl,
    box_body_piece_face_key as _box_body_piece_face_key_impl,
    refresh_box_body_piece_tabs_2d as _refresh_box_body_piece_tabs_2d_impl,
    on_box_body_piece_2d_tab_changed as _on_box_body_piece_2d_tab_changed_impl,
    on_box_body_piece_double_click as _on_box_body_piece_double_click_impl,
)
```

Use thin host seams:

```python
def _phase6_refresh_presence_ui(self, existing_parts=None):
    return _refresh_presence_ui_impl(self, existing_parts)

@staticmethod
def _box_body_piece_label(part_key):
    return _box_body_piece_label_impl(part_key)

@staticmethod
def _box_body_piece_face_key(part_key):
    return _box_body_piece_face_key_impl(part_key)

def _refresh_box_body_piece_tabs_2d(self, render_data):
    return _refresh_box_body_piece_tabs_2d_impl(self, render_data)

def _on_box_body_piece_2d_tab_changed(self, event=None):
    return _on_box_body_piece_2d_tab_changed_impl(self, event)

def on_box_body_piece_double_click(self, event=None):
    return _on_box_body_piece_double_click_impl(self, event)
```

Replace the inline Notebook construction in `setup_tab_z_ui()` with:

```python
self.box_body_piece_tabs = build_box_body_piece_selector(self, self.tab_z)
```

- [ ] **Step 3: Run the structural GREEN gate**

Run: `pytest -q tests/test_issue291_gui_phase2_t3_selector.py`
Expected: `5 PASS / 0 FAIL`; `gui.py <= 8520` and no inline Notebook construction.

### Task 3: Selection/presence parity and protected invariants

**Files:**
- Modify tests only if an existing characterization gap is found before production changes; otherwise no production scope expansion.

**Interfaces:**
- Consumes/Produces: no new product API; validates existing selector routing.

- [ ] **Step 1: Run headless characterization/regressions**

Run the applicable selector/workspace tests covering active-part, presence, receiving/vault routing, multipart child identity and hidden/visible state. Any failure must be classified against the accepted predecessor before changing code.

- [ ] **Step 2: Run Xvfb interaction regressions**

Validate receiving/vault transition parity, one top-level `箱身`, physical subtabs `左側板 / 後面板 / 右側板`, subtab-to-authoritative-active-part routing, visibility parity and existing double-click routing.

- [ ] **Step 3: Run protected invariant/drift checks**

Confirm no changes under `config.ini`, `基準檔/**`, `ae_engine/**`, `phase6_project_file.py`, `phase6_fold_profiles.py`, manufacturing geometry/DXF authority or project schema.

- [ ] **Step 4: Remove temporary QA/execution helpers and re-run final applicable L0-L4 evidence**

Expected: all applicable evidence GREEN, or only exact candidate/baseline A/B-proven inherited baseline reds.

- [ ] **Step 5: Record accepted branch/HEAD and close #291**

Do not start #292 until #291 is accepted/closed.
