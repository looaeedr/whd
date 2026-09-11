import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
GUI = Path("gui.py")


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _function(path, name):
    matches = [
        node
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    assert len(matches) == 1, (path, name, len(matches))
    return matches[0]


def _named_calls(node):
    return [
        call.func.id
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    ]


def _self_calls(node):
    return [
        call.func.attr
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
    ]


def test_leaving_corner_data_for_a_real_part_hides_corner_data_panel():
    node = _function(BRIDGE, "_fix11_activate_part")
    source = ast.get_source_segment(BRIDGE.read_text(encoding="utf-8"), node) or ""
    assert "corner_data_panel" in source
    assert "pack_forget" in source


def test_live_family_switch_refreshes_corner_data_navigation_in_same_transaction():
    node = _function(BRIDGE, "_phase6_on_baseline_model_changed")
    assert "_phase6_refresh_corner_data_parts_panel" in _named_calls(node)


def test_corner_data_info_label_has_readable_base_font():
    node = _function(BRIDGE, "_phase6_prepare_corner_data_canvas")
    label_calls = [
        call
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Attribute)
        and isinstance(call.func.value.value, ast.Name)
        and call.func.value.value.id == "original"
        and call.func.value.attr == "ttk"
        and call.func.attr == "Label"
    ]
    assert label_calls
    fonts = [kw.value for call in label_calls for kw in call.keywords if kw.arg == "font"]
    assert fonts, "Corner Data info label needs an explicit readable base font"
    font = fonts[0]
    assert isinstance(font, (ast.Tuple, ast.List)) and len(font.elts) >= 2
    assert isinstance(font.elts[1], ast.Constant)
    assert float(font.elts[1].value) >= 11.0


def test_corner_data_renderer_uses_compact_viewport_reserved_space():
    node = _function(GUI, "_render_fold_designer_corner_data_view")
    viewport_calls = [
        call
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_phase6_2d_material_viewport"
    ]
    assert len(viewport_calls) == 1
    keywords = {kw.arg: kw.value for kw in viewport_calls[0].keywords if kw.arg}
    assert "top_gutter" in keywords
    assert isinstance(keywords["top_gutter"], ast.Constant)
    assert float(keywords["top_gutter"].value) <= 72.0


def test_corner_data_renderer_keeps_authoritative_scene_path_without_duplicate_summary():
    node = _function(GUI, "_render_fold_designer_corner_data_view")
    named = _named_calls(node)
    methods = _self_calls(node)
    assert "render_drawing_scene" in named
    assert "_draw_phase6_annotation_projection" in named
    assert "_draw_phase6_finished_dimension_summary" not in methods
