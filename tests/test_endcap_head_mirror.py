import math

import ae_engine.ae as ae
from ae_engine.sheetmetal_drawing import PolylinePrimitive, LinePrimitive, CirclePrimitive
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_part_adapters import build_endcap_result


def _xy(point):
    return (round(point.x, 9), round(point.y, 9))


def _mirror_y(point, height):
    return (round(point.x, 9), round(height - point.y, 9))


def _first(scene, cls, layer):
    return next(p for p in scene.primitives if isinstance(p, cls) and p.layer == layer)


def _params():
    return dict(w=500.0, d=250.0, t=2.0, fw=25.0, yl1=15.0, yr1=17.0, ytop1=16.0, ybottom1=15.0)


def test_head_structural_outline_is_vertical_mirror_but_tail_is_not():
    p = _params()
    result = build_endcap_result(**p, relief_config=ae.RELIEF_CONFIG)

    head = ae._build_end_cap_scene(**p, is_tail=False)
    tail = ae._build_end_cap_scene(**p, is_tail=True)

    head_outline = _first(head, PolylinePrimitive, "CUTTING")
    tail_outline = _first(tail, PolylinePrimitive, "CUTTING")

    assert [_xy(pt) for pt in tail_outline.points] == [_xy(pt) for pt in result.outline]
    assert [_xy(pt) for pt in head_outline.points] == [_mirror_y(pt, result.height) for pt in result.outline]


def test_head_bend_lines_and_fixed_features_follow_same_vertical_mirror():
    p = _params()
    result = build_endcap_result(**p, relief_config=ae.RELIEF_CONFIG)
    head = ae._build_end_cap_scene(**p, is_tail=False)
    tail = ae._build_end_cap_scene(**p, is_tail=True)

    head_bends = [x for x in head.primitives if isinstance(x, LinePrimitive) and x.layer == "BEND"]
    tail_bends = [x for x in tail.primitives if isinstance(x, LinePrimitive) and x.layer == "BEND"]
    assert len(head_bends) == len(tail_bends)
    for hb, tb in zip(head_bends, tail_bends):
        assert _xy(hb.p1) == _mirror_y(tb.p1, result.height)
        assert _xy(hb.p2) == _mirror_y(tb.p2, result.height)

    # Shared hanging/square fixed features must move with the whole head scene.
    head_circles = [x for x in head.primitives if isinstance(x, CirclePrimitive) and x.layer == "CUTTING"]
    tail_circles = [x for x in tail.primitives if isinstance(x, CirclePrimitive) and x.layer == "CUTTING"]
    # Tail has one extra bottom-center circle; compare the two shared hanging holes.
    assert len(head_circles) + 1 == len(tail_circles)
    for hc, tc in zip(head_circles[:2], tail_circles[:2]):
        assert _xy(hc.center) == _mirror_y(tc.center, result.height)
        assert math.isclose(hc.radius, tc.radius)


def test_head_preview_uses_pre_normalized_scene_without_render_time_mirror(monkeypatch):
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = gui.BoxCalculatorGUI(root)
    try:
        root.deiconify()
        root.geometry("1100x750")
        app.baseline_var.set("")
        app.notebook.select(app.tab_head)
        root.update()
        val = app.get_float_values()

        def forbidden_preview_transform(*args, **kwargs):
            raise AssertionError("head preview must not mirror at render time")

        rendered = []
        monkeypatch.setattr(gui, "_YMirroredPreviewTransform", forbidden_preview_transform)
        monkeypatch.setattr(gui, "render_drawing_scene", lambda canvas, scene, transform, **kwargs: rendered.append(scene))

        app.draw_end_cap(val, app.canvas_head, "封頭", is_tail=False)
        assert len(rendered) == 1

        expected = ae._build_end_cap_scene(
            w=val['w'], d=val['d'], t=val['t'], fw=val['fw'],
            yl1=val['yl1'], yr1=val['yr1'], ytop1=val['ytop1'], ybottom1=val['ybottom1'],
            draw_stock=app.draw_stock_var.get(), is_tail=False, holes=app.head_holes,
        )
        actual_outline = _first(rendered[0], PolylinePrimitive, "CUTTING")
        expected_outline = _first(expected, PolylinePrimitive, "CUTTING")
        assert [_xy(p) for p in actual_outline.points] == [_xy(p) for p in expected_outline.points]
    finally:
        root.destroy()


def test_stretched_head_scene_is_normalized_once_and_export_does_not_mirror_again(monkeypatch, tmp_path):
    from ae_engine.sheetmetal_drawing import DrawingScene, SceneData

    raw = DrawingScene()
    raw.add_polyline([(0, 0), (10, 0), (10, 20), (0, 20)], layer="CUTTING", closed=True)
    raw.add_line((2, 3), (8, 3), layer="BEND")
    params = {
        'yl1': 15.0, 'yr1': 15.0, 'ytop1': 15.0, 'ybottom1': 15.0, 'fw': 25.0,
        'total_width': 10.0, 'total_depth': 20.0,
    }

    monkeypatch.setattr(
        ae,
        "get_stretched_end_cap_data",
        lambda *args, **kwargs: SceneData(scene=raw, params=dict(params)),
    )
    monkeypatch.setattr(ae, "build_endcap_check", lambda **kwargs: ())
    monkeypatch.setattr(ae, "_resolve_user_holes", lambda *args, **kwargs: ())

    built = ae._build_stretched_end_cap_scene(
        "dummy", 500.0, 500.0, 250.0, 2.0, 25.0,
        draw_stock=False, is_tail=False, holes=None,
    )
    built_outline = _first(built.scene, PolylinePrimitive, "CUTTING")
    assert [_xy(p) for p in built_outline.points] == [
        (0.0, 20.0), (10.0, 20.0), (10.0, 0.0), (0.0, 0.0)
    ]
    assert built.metadata.get("orientation_normalized") is True

    captured = []
    monkeypatch.setattr(ae, "_build_stretched_end_cap_scene", lambda *args, **kwargs: built)
    monkeypatch.setattr(ae, "_save_scene_dxf", lambda filepath, scene: captured.append(scene))

    ae.export_stretched_end_cap_dxf(
        tmp_path / "head.dxf", "dummy",
        W_val=500.0, H_val=500.0, D_val=250.0, T_val=2.0, FW_val=25.0,
        draw_stock=False, is_tail=False, holes=None,
    )
    assert len(captured) == 1
    exported_outline = _first(captured[0], PolylinePrimitive, "CUTTING")
    assert [_xy(p) for p in exported_outline.points] == [_xy(p) for p in built_outline.points]


def test_head_user_hole_is_resolved_in_final_wysiwyg_orientation():
    """A hole edited at y on the head finished face must stay at that visual y after scene rebuild."""
    from dataclasses import replace
    from ae_engine.sheetmetal_features import endcap_feature_context_from_geometry, legacy_hole_to_feature, resolve_endcap_features

    p = _params()
    hole = {"type": "圓形", "x": 120.0, "y": 40.0, "params": {"diameter": 13.0}}
    result = build_endcap_result(**p, relief_config=ae.RELIEF_CONFIG)
    raw_ctx = endcap_feature_context_from_geometry(result.topology, p["w"], p["d"])
    final_ctx = replace(raw_ctx, bottom_fold=result.height - raw_ctx.unfolded_flat_top)
    expected = resolve_endcap_features(final_ctx, [legacy_hole_to_feature(hole)])[0]

    head = ae._build_end_cap_scene(**p, is_tail=False, holes=[hole])
    user_circle = next(
        primitive for primitive in head.primitives
        if isinstance(primitive, CirclePrimitive)
        and primitive.layer == "CUTTING"
        and math.isclose(primitive.radius, 6.5)
    )

    assert _xy(user_circle.center) == _xy(expected.center)
