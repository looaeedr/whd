# -*- coding: utf-8 -*-
"""#1503 real Receiving left/right side 2D display-only EAR wiring."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from shapely.geometry import box

from ae_engine.receiving_fixed_plate_side_contact import (
    resolve_receiving_ear_side_contact_surfaces,
)
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive
from gui_modules.application.receiving_ear_side_2d import (
    present_receiving_ear_side_piece_2d,
    project_receiving_ear_side_piece_2d_preview,
)
from tests.test_issue1384_scene_access import _fixture
from tests.test_issue1503_real_side_uv_backprojection import _project
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _side_geometry():
    original = _fixture()
    body = original.parts[1].render_data
    pieces = tuple(replace(
        p, role=str(p.role).lower(), render_data=replace(
            p.render_data,
            material=box(0, 0, 1500, 1500),
            scene=DrawingScene(),
            metadata={"manufacturing_ready": False, "baseline_source_sha256": "source-side"},
        ),
    ) for p in body.pieces)
    assembled_body = replace(body, pieces=pieces)
    geometry = replace(original, parts=(
        original.parts[0],
        replace(original.parts[1], render_data=assembled_body),
    ))
    return geometry, pieces


def _receipts():
    return tuple(_project(c) for c in resolve_receiving_ear_side_contact_surfaces(_assembled()))


def test_actual_side_uv_receipts_appear_on_display_copy_not_manufacturing(monkeypatch):
    import gui_modules.application.receiving_ear_side_2d as live
    geometry, pieces = _side_geometry()
    rows = _receipts()
    monkeypatch.setattr(live, "resolve_receiving_ear_side_uv_receipts",
                        lambda snapshot, **kw: rows)
    shown = project_receiving_ear_side_piece_2d_preview(
        _assembled(), pieces[0], piece_key="box_body:left_side",
        geometry=geometry, dimensions=(800,1600,350), sheet_thickness=2,
        world_geometry={},
    )
    assert shown is not pieces[0]
    assert shown.render_data is not pieces[0].render_data
    assert shown.render_data.material is pieces[0].render_data.material
    assert shown.render_data.metadata["ear_side_mark_preview_only"] is True
    assert shown.render_data.metadata["ear_side_mark_preview_count"] == 4
    assert shown.render_data.metadata["manufacturing_ready"] is False
    assert len(shown.render_data.scene.primitives) == 4
    assert all(isinstance(x, LinePrimitive) and x.layer == "MARKING"
               for x in shown.render_data.scene.primitives)
    assert pieces[0].render_data.scene.primitives == []
    assert geometry.parts[1].render_data.pieces[0].render_data.scene.primitives == []


def test_wrong_side_source_and_drift_fail_without_a_fake_display(monkeypatch):
    import gui_modules.application.receiving_ear_side_2d as live
    geometry, pieces = _side_geometry()
    monkeypatch.setattr(live, "resolve_receiving_ear_side_uv_receipts",
                        lambda *args, **kw: _receipts())
    kwargs = dict(geometry=geometry, dimensions=(800,1600,350),
                  sheet_thickness=2, world_geometry={})
    with pytest.raises(ValueError, match="PIECE_ROLE_MISMATCH"):
        project_receiving_ear_side_piece_2d_preview(
            _assembled(), pieces[0], piece_key="box_body:right_side", **kwargs,
        )
    stale = replace(
        pieces[0], render_data=replace(
            pieces[0].render_data, material=box(0, 0, 1400, 1500),
        ),
    )
    with pytest.raises(ValueError, match="SOURCE_AND_MANUFACTURING_SIDE_DRIFT"):
        project_receiving_ear_side_piece_2d_preview(
            _assembled(), stale, piece_key="box_body:left_side", **kwargs,
        )
    with pytest.raises(ValueError, match="REQUIRES_SUBMITTED"):
        project_receiving_ear_side_piece_2d_preview(
            {**_assembled(), "nfb_config_submitted": False},
            pieces[0], piece_key="box_body:left_side", **kwargs,
        )


def test_live_selected_piece_2d_cache_and_blocker_do_not_break_regular_preview(monkeypatch):
    import gui_modules.application.receiving_ear_side_2d as live
    geometry, pieces = _side_geometry()
    snapshot = _assembled()
    host = SimpleNamespace(
        _compose_phase6_project_snapshot_from_main_gui=lambda: snapshot,
    )
    shown = replace(pieces[0], render_data=replace(
        pieces[0].render_data,
        metadata={**pieces[0].render_data.metadata, "ear_side_mark_preview_only": True},
    ))
    calls = []
    def make_preview(*args, **kwargs):
        calls.append(1)
        return shown
    monkeypatch.setattr(live, "project_receiving_ear_side_piece_2d_preview", make_preview)
    provider = lambda _host: geometry
    a, error = present_receiving_ear_side_piece_2d(
        host, geometry.parts[1].render_data, pieces[0], "box_body:left_side",
        geometry_provider=provider,
    )
    assert a is shown and error is None
    b, error = present_receiving_ear_side_piece_2d(
        host, geometry.parts[1].render_data, pieces[0], "box_body:left_side",
        geometry_provider=provider,
    )
    assert b is shown and error is None and len(calls) == 1
    snapshot = {**snapshot, "receiving_inner_door_layer_heights_mm": [330,830]}
    present_receiving_ear_side_piece_2d(
        host, geometry.parts[1].render_data, pieces[0], "box_body:left_side",
        geometry_provider=provider,
    )
    assert len(calls) == 2

    def blocked(*args, **kwargs):
        raise ValueError("EAR_SIDE_UV_CUTTING_OR_MATERIAL_CONFLICT")
    monkeypatch.setattr(live, "project_receiving_ear_side_piece_2d_preview", blocked)
    snapshot = {**snapshot, "receiving_inner_door_layer_heights_mm": [340,840]}
    fallback, reason = present_receiving_ear_side_piece_2d(
        host, geometry.parts[1].render_data, pieces[0], "box_body:left_side",
        geometry_provider=provider,
    )
    assert fallback is pieces[0] and "CUTTING_OR_MATERIAL_CONFLICT" in reason
    assert pieces[0].render_data.scene.primitives == []


def test_existing_gui_render_snapshot_consumes_only_selected_side_copy(monkeypatch):
    from gui_modules.application import render_snapshots
    from gui_modules.application import receiving_ear_side_2d as live
    geometry, pieces = _side_geometry()
    composite = geometry.parts[1].render_data
    copy = replace(pieces[0], render_data=replace(
        pieces[0].render_data,
        metadata={**pieces[0].render_data.metadata, "ear_side_mark_preview_only": True},
    ))
    monkeypatch.setattr(live, "present_receiving_ear_side_piece_2d",
                        lambda *args: (copy, None))
    host = SimpleNamespace(
        _box_body_part_spec=lambda values: "source",
        _manufacturing_context=lambda **kwargs: "context",
        _authoritative_render_data=lambda spec,ctx: composite,
        _refresh_box_body_piece_tabs_2d=lambda data: "box_body:left_side",
    )
    result = render_snapshots.box_body_render_snapshot(host, {"w":800,"h":1600,"d":350})
    assert result["mode"] == "piece"
    assert result["piece"] is copy
    assert result["render_data"] is composite
    assert result["ear_marking_preview_blocker"] is None


def test_real_box_body_piece_canvas_receives_preview_marks_and_unapproved_label():
    from gui_modules.rendering.box_body_view import draw_box_body_piece_preview

    geometry, pieces = _side_geometry()
    shown = replace(pieces[0], render_data=replace(
        pieces[0].render_data,
        metadata={**pieces[0].render_data.metadata,
                  "ear_side_mark_preview_only": True,
                  "ear_side_mark_preview_count": 4},
    ))
    class Canvas:
        def __init__(self):
            self.messages = []
        def winfo_width(self): return 900
        def winfo_height(self): return 700
        def create_text(self, *args, **kwargs): self.messages.append(kwargs.get("text",""))
    canvas=Canvas()
    host = SimpleNamespace(
        canvas_z=canvas,
        draw_stock_var=SimpleNamespace(get=lambda: False),
        _box_body_piece_label=lambda key: "左側板",
        COLOR_TEXT_MUTED="#ffffff",
    )
    viewed = []
    draw_box_body_piece_preview(
        host, geometry.parts[1].render_data, shown, "box_body:left_side",
        viewport=lambda *args: (object(), 0, 0, 1, 0),
        scene_renderer=lambda canvas, scene, transform, **kw: viewed.append(scene),
        annotation_drawer=lambda *args, **kwargs: None,
    )
    assert viewed == [shown.render_data.scene]
    assert any("MARKING 預覽" in message and "未核准製造" in message
               for message in canvas.messages)
    assert len(canvas.messages) == 1


def test_real_receiving_box_side_source_world_uv_produces_actual_2d_marks():
    """No mocked world triangles, UV solver, source panels or fixture scene."""
    from tests.test_issue1050_receiving_mother_plate_marking import (
        _snapshot as real_box_snapshot, _full_receiving_geometry,
    )

    snapshot = real_box_snapshot()
    snapshot.update(_assembled())
    geometry = _full_receiving_geometry(snapshot)
    body = geometry.part("box_body").render_data
    side_by_role = {str(piece.role).lower(): piece for piece in body.pieces}
    assert set(side_by_role) >= {"left_side", "right_side"}

    for role in ("left_side", "right_side"):
        owner = side_by_role[role]
        shown = project_receiving_ear_side_piece_2d_preview(
            snapshot, owner, piece_key="box_body:" + role,
            geometry=geometry, dimensions=(800., 1600., 350.),
            sheet_thickness=2.,
        )
        assert shown.render_data.metadata["ear_side_mark_preview_count"] == 4
        assert sum(p.layer == "MARKING" for p in shown.render_data.scene.primitives) >= 4
        assert shown.render_data.material.equals(owner.render_data.material)
        assert shown.render_data is not owner.render_data
