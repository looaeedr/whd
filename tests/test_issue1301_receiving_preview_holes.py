from __future__ import annotations

import ast
import inspect
from pathlib import Path

from gui_modules.application import receiving_set_bay_controls as controls

ROOT = Path(__file__).resolve().parents[1]


def _class_method_source(path: Path, class_name: str, method_name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return ast.get_source_segment(text, item) or ""
    raise AssertionError(f"missing method: {class_name}.{method_name}")


def _class_method_source_any(path: Path, method_name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == method_name:
                return ast.get_source_segment(text, item) or ""
    raise AssertionError(f"missing class method: {method_name}")


def test_receiving_preview_exposes_2d_zoom_pan_and_part_visibility_controls():
    from gui_modules.application.receiving_settings_preview_2d import ReceivingSettingsPreview2D
    # Only the settings surface changes renderer; committed manufacturing
    # requests remain owned by the original composition owner.
    source = inspect.getsource(controls.open_receiving_layer_preview)
    assert "ReceivingSettingsPreview2D(" in source
    assert "Phase6FinalSceneRenderer" not in source
    assert 'text="放大"' in source
    assert 'text="縮小"' in source
    assert 'text="重設視角"' in source
    view = inspect.getsource(ReceivingSettingsPreview2D)
    assert 'mpl_connect("scroll_event"' in view
    assert 'ttk.Checkbutton(' in view
    assert "data.scene.primitives" in view
    assert "readfile" not in view and "projection=\"3d\"" not in view


def _module_function_source(path: Path, method_name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == method_name
    )
    return ast.get_source_segment(source, node) or ""


def test_rear_panel_selector_is_promoted_into_same_receiving_header_as_switch():
    controls_source = (ROOT / "gui_modules" / "application" / "receiving_set_bay_controls.py").read_text(
        encoding="utf-8"
    )
    bridge_source = (ROOT / "fold_designer_bridge.py").read_text(encoding="utf-8")
    owner_path = ROOT / "gui_modules" / "application" / "fold_designer_composition_receiving.py"
    applicability = _module_function_source(
        owner_path, "back_panel_mode_control_is_applicable"
    )
    refresh = _module_function_source(
        owner_path, "refresh_back_panel_mode_control"
    )

    assert "header: object" in controls_source
    assert "header=header" in controls_source
    assert "Frame(receiving_controls.header)" in bridge_source
    assert 'text="後面板形式"' in bridge_source
    assert 'active_part != "box_body:back"' not in applicability
    assert 'canonical_family_name(snapshot) != "受電箱"' in applicability
    assert "frame.pack(side=original.tk.LEFT" in refresh


def test_rear_panel_keeps_real_cutting_rims_without_wireframe_overlays():
    renderer = (ROOT / "phase6_final_scene_renderer.py").read_text(encoding="utf-8")
    assert 'if piece_role == "back":' in renderer
    assert "self._add_mesh_feature_lines(piece_placed, edge)" in renderer
    assert 'if piece_role == "back":\n                continue' in renderer
    assert "self._draw_joint_marking_world_rows(piece.render_data)" in renderer


def test_receiving_door_status_uses_shared_family_baseline_and_family_fw_semantics():
    source = _class_method_source_any(ROOT / "gui.py", "_door_layout_baseline_scene")
    assert "baseline_feature_model_name(family_model)" in source
    assert 'ae.has_baseline_part(baseline_model, "門.dxf")' in source
    assert "model_name=family_model" in source
    assert "door_nameplate_center_datum_top" in source
    assert 'ae.baseline_source_label(baseline_model, "門.dxf")' in source


def test_phase6_hole_editor_close_is_safe_without_legacy_door_canvas():
    source = _class_method_source_any(ROOT / "gui.py", "draw_door_layout_overview")
    assert 'getattr(self, "canvas_door", None)' in source
    assert "if canvas is None:" in source
    assert "return None" in source


def test_settings_mousewheel_tolerates_tk_unknown_event_number():
    source = _class_method_source_any(ROOT / "phase6_settings_panel.py", "_scroll_settings_fields")
    assert "except (TypeError, ValueError):" in source
    assert "number = 0" in source
