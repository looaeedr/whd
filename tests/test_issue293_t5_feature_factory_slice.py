from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
TARGET_CALLBACK = "make_feature"


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


def _factory_class():
    tree = ast.parse(EDITOR.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorFeatureFactory"), None)
    assert node is not None, "T5 RED: HoleEditorFeatureFactory is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns: dict[str, object] = {}
    exec(compile(module, str(EDITOR), "exec"), ns)
    return ns["HoleEditorFeatureFactory"]


class _Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value


def _build(*, label="Catalog A", context=None, catalog=None, rotation="90°"):
    cls = _factory_class()
    calls = {"circle": [], "rect": [], "feature": [], "anchor": [], "errors": []}
    context_box = context if context is not None else {"width": 800.0, "height": 600.0}
    catalog_map = {"Catalog A": "DEF-A"} if catalog is None else catalog

    def custom_circle(diameter, blind=False):
        calls["circle"].append((diameter, blind))
        return ("CIRCLE", diameter, blind)

    def custom_rect(width, height, blind=False):
        calls["rect"].append((width, height, blind))
        return ("RECT", width, height, blind)

    def from_definition(definition, point, width, height, rotation_deg=0):
        calls["feature"].append((definition, point, width, height, rotation_deg))
        return ("FEATURE", definition, point)

    def with_anchor(feature, anchor):
        calls["anchor"].append((feature, anchor))
        return ("ANCHORED", feature, anchor)

    factory = cls(
        selected_catalog_text=_Var(label),
        rotation_var=_Var(rotation),
        diameter_var=_Var("12.5"),
        width_var=_Var("20"),
        height_var=_Var("30"),
        blind_var=_Var(True),
        context_provider=lambda: context_box,
        catalog_by_label=catalog_map,
        custom_circle_definition=custom_circle,
        custom_rectangle_definition=custom_rect,
        feature_from_definition=from_definition,
        feature_with_reference_anchor=with_anchor,
        center_anchor="CENTER",
        show_error=lambda title, text: calls["errors"].append((title, text)),
    )
    return factory, calls, context_box


def test_make_feature_callback_moves_out_of_unified_root():
    assert TARGET_CALLBACK not in _unified_nested_names(), "T5 RED: make_feature remains rooted"
    tree = ast.parse(EDITOR.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorFeatureFactory"), None)
    assert cls is not None, "T5 RED: HoleEditorFeatureFactory is missing"
    assert _span(cls) <= 80
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "make_feature")
    assert _span(method) <= 35


def test_gui_wiring_uses_live_size_context_provider():
    composition = (ROOT / "gui_modules" / "editors" / "hole_editor_composition.py").read_text(encoding="utf-8")
    assert '"width": s.live_context.width' in composition
    assert '"height": s.live_context.height' in composition
    assert "s.make_feature = feature_factory.make_feature" in composition

def test_catalog_definition_delegates_geometry_and_center_anchor():
    factory, calls, _ = _build()
    result = factory.make_feature("P")
    assert calls["feature"] == [("DEF-A", "P", 800.0, 600.0, 90)]
    assert calls["anchor"] == [(('FEATURE', 'DEF-A', 'P'), "CENTER")]
    assert calls["errors"] == []
    assert result == ("ANCHORED", ("FEATURE", "DEF-A", "P"), "CENTER")


def test_custom_circle_and_rectangle_keep_definition_authority_delegated():
    circle, circle_calls, _ = _build(label="＋ 自訂圓孔")
    assert circle.make_feature("PC") is not None
    assert circle_calls["circle"] == [(12.5, True)]
    assert circle_calls["feature"][0][0] == ("CIRCLE", 12.5, True)

    rect, rect_calls, _ = _build(label="＋ 自訂方孔")
    assert rect.make_feature("PR") is not None
    assert rect_calls["rect"] == [(20.0, 30.0, True)]
    assert rect_calls["feature"][0][0] == ("RECT", 20.0, 30.0, True)


def test_factory_reads_context_late_and_preserves_user_error_path():
    factory, calls, context = _build()
    context["width"] = 910.0
    context["height"] = 710.0
    assert factory.make_feature("P2") is not None
    assert calls["feature"][0][2:4] == (910.0, 710.0)

    missing, missing_calls, _ = _build(label="missing", catalog={})
    assert missing.make_feature("P3") is None
    assert missing_calls["feature"] == []
    assert missing_calls["errors"] == [("開孔錯誤", "請先從左側選擇孔型")]
