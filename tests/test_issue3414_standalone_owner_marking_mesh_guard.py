"""A 3D view mesh may bound visible ink, but cannot remanufacture a mark."""
from types import SimpleNamespace

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry import Vec2


def test_coverage_is_for_the_whole_projected_stroke_not_two_valid_ends():
    # Flat identity profile centers each 10mm axis. There is a physical
    # 0.2mm gap between two displayed faces, smaller than the sampling step.
    def square(a,b):
        return (
            ((a,-1,0),(b,-1,0),(a,1,0)),
            ((a,1,0),(b,-1,0),(b,1,0)),
        )

    automatic = LinePrimitive(Vec2(5.1,5), Vec2(5.2,5), "MARKING")
    authored = PolylinePrimitive(
        (Vec2(5.1,5), Vec2(5.9,5)), "MARKING", False, 211, "WHD_MANUAL_MARKING_V1",
    )
    scene = DrawingScene([automatic, authored])
    mesh = SimpleNamespace(x_profile=({"len":10},), y_profile=({"len":10},),
                           fold_guides=(), triangles=square(0,0.4)+square(0.6,1))
    paths, warning = api.project_checked_owner_marking_standalone_paths(scene, mesh)
    assert len(paths) == 1 and warning == "OWNER_MARKING_STANDALONE_SURFACE_UNPROVED"
    mesh.triangles = square(0,0.5)+square(0.5,1)
    paths, warning = api.project_checked_owner_marking_standalone_paths(scene, mesh)
    assert len(paths) == 2 and warning is None
    assert tuple(scene.primitives) == (automatic, authored)


def test_dense_typed_ordinary_ink_is_withheld_without_projecting_any_authored_path(monkeypatch):
    from ae_engine.operator_manual_marking import _build_manual_straight_feature
    from ae_engine import operator_owner_marking_3d_view as view

    # A genuine 600-mm authored line with 8000 0.0375-mm dashes is legal
    # typed intent. Only standalone display work is bounded.
    dense = _build_manual_straight_feature(Vec2(400, 20), 600, 0, "dashed", 0.0375, 0.0375)
    wide = _build_manual_straight_feature(Vec2(400, 20), 600, 0, "solid", 10, 5)
    assert len(dense.layered_profiles) == 8000
    assert not view.within_standalone_marking_budget((dense,), 9)
    assert view.within_standalone_marking_budget((wide,), 9, 134)
    assert not view.within_standalone_marking_budget((wide,), 9, 300)

    automatic = LinePrimitive(Vec2(1,1), Vec2(2,2), "MARKING")
    full_ink = tuple(PolylinePrimitive(points, layer, closed, 211, "WHD_MANUAL_MARKING_V1")
                     for layer, points, closed in dense.layered_profiles)
    scene = DrawingScene([automatic, *full_ink])
    calls = []
    original = view.project_independent_scene_annotation_paths

    def observe(source, *args):
        calls.append(tuple(source.primitives))
        return original(source, *args)

    monkeypatch.setattr(view, "project_independent_scene_annotation_paths", observe)
    mesh = SimpleNamespace(x_profile=({"len":800},), y_profile=({"len":400},),
                           fold_guides=(), triangles=())
    paths, warning = api.project_checked_owner_marking_standalone_paths(scene, mesh)
    assert calls == [(automatic,)]
    assert len(paths) == 1 and warning == api.OWNER_MARKING_3D_PREVIEW_BUDGET
    assert tuple(scene.primitives) == (automatic, *full_ink)
