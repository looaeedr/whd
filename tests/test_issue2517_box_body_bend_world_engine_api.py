"""#2517 BoxBody BEND world-segment source must be public headless Engine."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from shapely.geometry import box

from ae_engine import (
    manufacturing_api, contract_fold_profile_rows,
    project_assembly_box_body_bend_segments,
    project_box_body_structure_bend_segments,
)
from ae_engine.assembly_geometry import (
    place_assembly_points, place_box_body_structure_points,
)
from ae_engine.sheetmetal_drawing import DrawingScene
from phase6_final_scene_projection import _phase6_contract_profile_rows
from phase6_final_scene_render_helpers import Phase6FinalSceneRenderHelpersMixin


def _scene():
    scene = DrawingScene()
    scene.add_line((20, 10), (20, 70), layer="BEND")
    scene.add_line((20, 40), (80, 40), layer="BEND")
    scene.add_line((5, 5), (95, 5), layer="MARKING")
    return scene


def _profiles():
    return ([{"len": 100.0, "core": "W"}],
            [{"len": 80.0, "core": "D"}], ())


def _reference():
    return (((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (0.0, 80.0, 0.0)),)


def _piece(role="left", start=0.0, end=100.0):
    fold = (SimpleNamespace(
        length=100.0, angle=None, core="W", phase6_key="w",
    ),)
    return SimpleNamespace(
        role=role, formed_w_start=start, formed_w_end=end,
        formed_y_offset=0.0, fold_profile=fold,
        render_data=SimpleNamespace(
            material=box(0, 0, 100, 80), scene=_scene(), fold_guides=(),
        ),
    )


def test_one_sheet_world_bends_equal_canonical_assembly_transform():
    scene = _scene()
    x, y, guides = _profiles()
    # The canonical Fold mapper centers the core, even with zero bend angles.
    # Use fixed formed-space goldens, not uncentered flat CUTTING coordinates.
    original = (((-30.0, -30.0, 0.0), (-30.0, 30.0, 0.0)),
                ((-30.0, 0.0, 0.0), (30.0, 0.0, 0.0)))
    for placement in ("box_body", "door"):
        result = project_assembly_box_body_bend_segments(
            scene, x, y, guides, _reference(), placement, (100, 80, 40),
            (7, 8, 9),
        )
        assert len(result) == 2 and isinstance(result, tuple)
        assert result == tuple(
            place_assembly_points(line, _reference(), placement,
                                  (100, 80, 40), (7, 8, 9))
            for line in original
        )
    assert manufacturing_api.project_assembly_box_body_bend_segments is (
        project_assembly_box_body_bend_segments
    )
    assert project_assembly_box_body_bend_segments(
        scene, x, y, guides, (), "box_body", (100, 80, 40), (0, 0, 0),
    ) == ()


def test_physical_piece_world_bends_match_existing_placement_and_filters():
    left = _piece()
    back = _piece("back", 100, 200)
    right = _piece("right", 200, 300)
    render = SimpleNamespace(pieces=(left, back, right))
    rows = project_box_body_structure_bend_segments(
        render, thickness=2.0,
    )
    # Every visible side/band has two real source BEND lines; back is suppressed.
    assert len(rows) == 4
    x_profile = contract_fold_profile_rows(left.fold_profile)
    # The canonical Fold mapper centers the core, even with zero bend angles.
    # Use fixed formed-space goldens, not uncentered flat CUTTING coordinates.
    original = (((-30.0, -30.0, 0.0), (-30.0, 30.0, 0.0)),
                ((-30.0, 0.0, 0.0), (30.0, 0.0, 0.0)))
    assert rows[:2] == tuple(
        place_box_body_structure_points(line, left, total_w=300.0,
                                        thickness=2.0, x_profile=x_profile)
        for line in original
    )
    assert project_box_body_structure_bend_segments(
        render, thickness=2.0, visible_piece_keys={"box_body:left"},
    ) == rows[:2]
    placed = project_box_body_structure_bend_segments(
        render, thickness=2.0, local_reference=_reference(),
        placement="box_body", dimensions=(100, 80, 40), offset=(2, 3, 4),
        visible_piece_keys={"box_body:right"},
    )
    assert len(placed) == 2
    assert placed == tuple(
        place_assembly_points(line, _reference(), "box_body",
                              (100, 80, 40), (2, 3, 4))
        for line in rows[2:]
    )
    assert project_box_body_structure_bend_segments(
        SimpleNamespace(pieces=()), thickness=2,
    ) == ()


def test_fold_segment_original_rows_and_phase6_compatibility():
    profile = (
        SimpleNamespace(length=25, angle=-90, core=None, phase6_key="fw_left"),
        SimpleNamespace(length=100, angle=None, core="W", phase6_key=None),
    )
    expected = [
        {"len": 25.0, "angle": -90.0, "phase6_key": "fw_left"},
        {"len": 100.0, "core": "W"},
    ]
    assert contract_fold_profile_rows(profile) == expected
    assert _phase6_contract_profile_rows(profile) == expected
    assert manufacturing_api.contract_fold_profile_rows is contract_fold_profile_rows


def test_gui_draw_methods_are_api_only_and_keep_original_plot_attributes(monkeypatch):
    requests = []
    segment = (((1, 2, 3), (4, 5, 6)),)
    def single(*args):
        requests.append(("single", args))
        return segment
    def pieces(*args, **kwargs):
        requests.append(("pieces", args, kwargs))
        return segment
    monkeypatch.setattr(
        manufacturing_api, "project_assembly_box_body_bend_segments", single,
    )
    monkeypatch.setattr(
        manufacturing_api, "project_box_body_structure_bend_segments", pieces,
    )
    calls = []
    host = SimpleNamespace(
        renderer=SimpleNamespace(ax3d=SimpleNamespace(
            plot=lambda *args, **kwargs: calls.append((args, kwargs)),
        )),
    )
    x, y, guides = _profiles()
    Phase6FinalSceneRenderHelpersMixin._draw_assembly_box_body_bends(
        host, _scene(), x, y, guides, _reference(),
        "box_body", (100, 80, 40), (0, 0, 0),
    )
    Phase6FinalSceneRenderHelpersMixin._draw_box_body_structure_bends(
        host, SimpleNamespace(pieces=()), thickness=2,
        visible_piece_keys={"box_body:left"},
    )
    assert [call[0] for call in requests] == ["single", "pieces"]
    assert len(calls) == 2
    assert all(a == ([1, 4], [2, 5], [3, 6]) for a, _ in calls)
    assert all(kw == {
        "color": "#2563eb", "linewidth": 1.35,
        "linestyle": "-", "alpha": 0.98,
    } for _, kw in calls)
    for name, public in (
        ("_draw_assembly_box_body_bends", "project_assembly_box_body_bend_segments"),
        ("_draw_box_body_structure_bends", "project_box_body_structure_bend_segments"),
    ):
        method = getattr(Phase6FinalSceneRenderHelpersMixin, name)
        source = inspect.getsource(method)
        assert "manufacturing_api." + public + "(" in source
        for forbidden in ("self._map_xy(", "place_assembly_points(",
                          "place_box_body_structure_points(", "scene.primitives"):
            assert forbidden not in source


def test_engine_owner_never_imports_phase6_or_gui_or_tk():
    from ae_engine import final_scene_box_body_bend_lines as owner
    source = inspect.getsource(owner)
    assert "phase6_final_scene" not in source
    assert "gui_modules" not in source
    assert "matplotlib" not in source
    assert "tkinter" not in source
