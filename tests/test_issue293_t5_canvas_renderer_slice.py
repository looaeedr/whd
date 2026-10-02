from __future__ import annotations

import ast
from functools import partial
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
RENDERER = ROOT / "gui_modules" / "editors" / "hole_editor_render.py"
TARGETS = {"redraw", "draw_extra"}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


def _renderer_class():
    assert RENDERER.exists(), "T5 RED: hole_editor_render.py is missing"
    source = RENDERER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorCanvasRenderer"), None)
    assert node is not None, "T5 RED: HoleEditorCanvasRenderer is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns: dict[str, object] = {"partial": partial}
    exec(compile(module, str(RENDERER), "exec"), ns)
    return node, ns["HoleEditorCanvasRenderer"]


class _CanvasView:
    def __init__(self): self.frames = []
    def render(self, frame): self.frames.append(frame)


class _Frame:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)


class _Vec2:
    def __init__(self, x, y): self.x, self.y = x, y


class _ResolvedRect:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)


class _Transform:
    def world_to_canvas(self, p): return (p.x + 100.0, p.y + 200.0)


class _Canvas:
    def __init__(self): self.lines, self.texts = [], []
    def create_line(self, *args, **kwargs): self.lines.append((args, kwargs))
    def create_text(self, *args, **kwargs): self.texts.append((args, kwargs))


def _base_context():
    return {
        "surface": "SURFACE",
        "feature_list": ["F1"],
        "width": 800.0,
        "height": 600.0,
        "reference_guide": SimpleNamespace(
            min_point=SimpleNamespace(x=10.0, y=20.0),
            max_point=SimpleNamespace(x=810.0, y=620.0),
        ),
        "baseline_scene": "BASE",
        "active_part_key": "door",
        "indicator_box_dist_enabled": False,
        "indicator_mode_available": False,
        "door_indicator_context": None,
        "door_frame_width": None,
        "door_thickness": None,
        "door_gap_w": None,
        "door_gap_h": None,
        "door_frame_edges": None,
    }


def _build(context=None, indicator_state=None):
    _, cls = _renderer_class()
    context = _base_context() if context is None else context
    view = _CanvasView()
    calls = {
        "validate": [], "offsets": [], "render_features": [], "layout": [],
        "measure": [], "guides": [], "opening": [],
    }

    def frame_edges_factory():
        return SimpleNamespace(left=True, right=False, top=True, bottom=False)

    renderer = cls(
        context_provider=lambda: context,
        canvas_view=view,
        selected_index_provider=lambda: 2,
        reference_distances_provider=lambda: {"x": 1},
        measure_guide_provider=lambda: "MEASURE",
        selected_catalog_text_provider=lambda: "CAT",
        insert_mode_provider=lambda: True,
        error_text_provider=lambda: "ERR",
        collect_indicator_state=lambda: indicator_state,
        validate_current_indicator_fit=lambda show: calls["validate"].append(show) or True,
        door_enclosure_reference_offsets=lambda edges, **kwargs: calls["offsets"].append((edges, kwargs)) or {
            "left": 1.0, "bottom": 2.0, "right": 3.0, "top": 4.0,
        },
        door_frame_edges_factory=frame_edges_factory,
        vec2_factory=_Vec2,
        resolve_door_indicator_layout=lambda ctx, groups, offset: calls["layout"].append((ctx, groups, offset)) or SimpleNamespace(features=["LAMP"]),
        render_resolved_features=lambda canvas, features, tr, color=None: calls["render_features"].append((canvas, list(features), tr, color)),
        measure_door_indicator_position=lambda layout, ctx, **kwargs: calls["measure"].append((layout, ctx, kwargs)) or "POS",
        resolve_door_indicator_dimension_guides=lambda position: calls["guides"].append(position) or (
            SimpleNamespace(start=_Vec2(1, 2), end=_Vec2(3, 4), value=5.5),
            SimpleNamespace(start=_Vec2(6, 7), end=_Vec2(8, 9), value=10.5),
        ),
        indicator_box_opening_size=lambda groups, thickness: calls["opening"].append((groups, thickness)) or (111.0, 222.0),
        resolved_rect_factory=_ResolvedRect,
        canvas_frame_factory=_Frame,
        arrow_both="BOTH",
    )
    return renderer, view, calls, context


def test_redraw_and_draw_extra_move_out_of_unified_root():
    assert TARGETS.isdisjoint(_unified_nested_names()), "T5 RED: renderer callbacks remain rooted"
    node, _ = _renderer_class()
    assert _span(node) <= 230
    methods = {n.name: n for n in node.body if isinstance(n, ast.FunctionDef)}
    assert "redraw" in methods and "draw_extra" in methods
    assert _span(methods["redraw"]) <= 55
    assert _span(methods["draw_extra"]) <= 95


def test_gui_wiring_uses_one_live_render_context_provider():
    gui = GUI.read_text(encoding="utf-8")
    composition = (ROOT / "gui_modules" / "editors" / "hole_editor_composition.py").read_text(encoding="utf-8")
    assert "HoleEditorCanvasRenderer as _HoleEditorCanvasRenderer" in gui
    assert "canvas_renderer = d._HoleEditorCanvasRenderer(" in composition
    assert "s.redraw = canvas_renderer.redraw" in composition
    assert "s.indicator_redraw[0] = s.redraw" in composition
    for fragment in (
        '"feature_list": s.live_context.feature_list',
        '"surface": s.live_context.surface',
        '"width": s.live_context.width',
        '"height": s.live_context.height',
        '"reference_guide": s.live_context.reference_guide',
        '"baseline_scene": s.live_context.baseline_scene',
        '"active_part_key": s.active_part_key[0]',
    ):
        assert fragment in composition

def test_redraw_reads_context_late_and_builds_same_frame_contract():
    renderer, view, calls, context = _build()
    renderer.redraw()
    assert calls["validate"] == [False]
    assert len(view.frames) == 1
    first = view.frames[-1]
    assert (first.surface, first.features, first.width, first.height) == ("SURFACE", ["F1"], 800.0, 600.0)
    assert first.reference_guide is context["reference_guide"]
    assert first.selected_index == 2
    assert first.reference_distances == {"x": 1}
    assert first.measure_guide == "MEASURE"
    assert first.baseline_scene == "BASE"
    assert first.insert_label == "CAT"
    assert first.error_text == "ERR"
    assert callable(first.draw_extra)

    context["surface"] = "SURFACE-2"
    context["feature_list"] = ["F2"]
    context["width"] = 910.0
    context["height"] = 710.0
    renderer.redraw()
    second = view.frames[-1]
    assert (second.surface, second.features, second.width, second.height) == ("SURFACE-2", ["F2"], 910.0, 710.0)


def test_enclosure_bounds_and_indicator_box_overlay_stay_delegated():
    context = _base_context()
    context.update({
        "indicator_box_dist_enabled": True,
        "indicator_mode_available": True,
        "door_indicator_context": SimpleNamespace(
            left_fold=5.0, bottom_fold=7.0, finished_width=100.0, finished_height=80.0,
        ),
        "door_frame_width": 30.0,
        "door_thickness": 2.0,
        "door_gap_w": 3.0,
        "door_gap_h": 4.0,
    })
    state = {"mode": "indicator_box", "layers": 2, "groups": [3, 4, 9], "offset_x": 6.0, "offset_y": -8.0, "is_box_dist": True}
    renderer, view, calls, _ = _build(context=context, indicator_state=state)
    renderer.redraw()
    frame = view.frames[-1]
    assert frame.extra_bounds == (9.0, 18.0, 813.0, 624.0)
    canvas = _Canvas()
    frame.draw_extra(canvas, _Transform(), 1000, 800)
    assert calls["opening"] == [((3, 4), 2.0)]
    assert calls["render_features"][-1][1][0].width == 111.0
    assert calls["render_features"][-1][1][0].height == 222.0
    assert calls["render_features"][-1][3] == "#64d2ff"
    assert len(canvas.lines) == 4


def test_direct_indicator_overlay_delegates_layout_measurement_and_guides():
    context = _base_context()
    context.update({
        "indicator_box_dist_enabled": True,
        "indicator_mode_available": True,
        "door_indicator_context": SimpleNamespace(
            left_fold=5.0, bottom_fold=7.0, finished_width=100.0, finished_height=80.0,
        ),
        "door_frame_width": 30.0,
        "door_thickness": 2.0,
        "door_gap_w": 3.0,
        "door_gap_h": 4.0,
    })
    state = {"mode": "indicator", "layers": 1, "groups": [5, 9], "offset_x": 6.0, "offset_y": -8.0, "is_box_dist": True}
    renderer, view, calls, _ = _build(context=context, indicator_state=state)
    renderer.redraw()
    canvas = _Canvas()
    view.frames[-1].draw_extra(canvas, _Transform(), 1000, 800)
    assert calls["layout"][0][1] == (5,)
    assert calls["measure"] and calls["guides"] == ["POS"]
    assert calls["render_features"][0][1] == ["LAMP"]
    dimension_lines = [kwargs for _args, kwargs in canvas.lines if "indicator_dimension" in kwargs.get("tags", ())]
    assert len(dimension_lines) == 2
    assert all(kwargs.get("arrow") == "BOTH" for kwargs in dimension_lines)
