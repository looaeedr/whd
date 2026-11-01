# -*- coding: utf-8 -*-
"""#2517 repository-wide sweep: three GUI source-consumer chains use Engine."""
from __future__ import annotations

from inspect import getsource
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.operator_box_body_2d import BoxBodyAssemblyPanelPiece
from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, Vec2, feature_surface_from_rect,
)
import fold_designer_bridge as bridge
from gui_modules.application.receiving_settings_preview_2d import physical_drawings
from gui_modules.editors import cadcraft_preview_bridge as cadcraft


def test_boxbody_fold_designer_uses_same_engine_physical_inventory_as_assembly(monkeypatch):
    original = BoxBodyAssemblyPanelPiece(
        "box_body:left_side", 404.5, 500.0, 402.0, 498.0, object(),
    )
    render_data = object()
    calls = []
    def engine(data):
        calls.append(data)
        return (original,)
    monkeypatch.setattr(
        manufacturing_api, "project_box_body_assembly_panel_piece_rows", engine,
    )
    monkeypatch.setattr(bridge, "_phase6_part_label", lambda key: f"板件 {key}")
    rows = bridge._phase6_box_body_piece_dimension_projections(render_data)
    assert calls == [render_data]
    assert len(rows) == 1
    assert (rows[0].part_key, rows[0].formed_width, rows[0].formed_height,
            rows[0].blank_width, rows[0].blank_height) == (
                "box_body:left_side", 404.5, 500.0, 402.0, 498.0,
            )
    assert rows[0].label == "板件 box_body:left_side"
    # GUI must not recreate the physical role, dimensions, or source identity.
    source = getsource(bridge._phase6_box_body_piece_dimension_projections)
    assert "project_box_body_assembly_panel_piece_rows(" in source
    assert "formed_outer_dimensions" not in source
    assert "material_dimensions" not in source
    assert 'getattr(render_data, "pieces"' not in source


def test_receiving_settings_physical_source_readback_preserves_all_parts():
    left_source, back_source, door_source = object(), object(), object()
    left = SimpleNamespace(
        role="left_side", key="box_body:left_side", render_data=left_source,
    )
    back = SimpleNamespace(
        role="back", key="box_body:back", render_data=back_source,
    )
    parts = (
        SimpleNamespace(
            part_key="box_body",
            render_data=SimpleNamespace(pieces=(left, back)),
        ),
        SimpleNamespace(part_key="inner_door:1:panel", render_data=door_source),
    )
    expected = (
        ("left_side", "box_body:left_side", left_source),
        ("back", "box_body:back", back_source),
        ("inner_door:1:panel", "inner_door:1:panel", door_source),
    )
    assert manufacturing_api.project_receiving_settings_physical_drawings(parts) == expected
    request = SimpleNamespace(
        render_data=SimpleNamespace(assembly_parts=parts),
    )
    rows = tuple(physical_drawings(request))
    assert rows == (
        ("left_side", "box_body:left_side", left_source),
        ("back", "box_body:back", back_source),
        ("inner_door", "inner_door:1:panel", door_source),
    )
    assert manufacturing_api.project_receiving_settings_physical_drawings(()) == ()
    src = getsource(physical_drawings)
    assert "project_receiving_settings_physical_drawings(" in src
    assert 'getattr(part.render_data, "pieces"' not in src


def test_engine_cadcraft_check_preview_is_mm_and_not_cutting(tmp_path):
    surface = feature_surface_from_rect(
        "physical finished face", Vec2(0, 0), Vec2(100, 80),
    )
    holes = (
        CircleFeature(
            diameter=10, offset=Vec2(25, 30), layer="CUTTING",
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        ),
    )
    original = tuple(holes)
    scene = manufacturing_api.project_cadcraft_check_scene(
        surface=surface, features=holes, width=100, height=80,
    )
    assert isinstance(scene, DrawingScene)
    assert scene.primitives and all(x.layer == "CHECK" for x in scene.primitives)
    assert cadcraft.build_hole_editor_cadcraft_scene(
        surface=surface, features=holes, width=100, height=80,
    ).primitives == scene.primitives
    path = tmp_path / "cadcraft-check.dxf"
    manufacturing_api.save_cadcraft_check_scene_dxf(path, scene)
    reopened = ezdxf.readfile(path)
    assert reopened.header["$INSUNITS"] == 4
    assert reopened.header["$MEASUREMENT"] == 1
    entities = tuple(reopened.modelspace())
    assert entities and all(x.dxf.layer == "CHECK" for x in entities)
    circles = [e for e in entities if e.dxftype() == "CIRCLE"]
    assert len(circles) == 1
    assert (circles[0].dxf.center.x, circles[0].dxf.center.y) == pytest.approx((25, 30))
    assert circles[0].dxf.radius == pytest.approx(5)
    assert tuple(holes) == original

    # The original GUI button's compatibility saver uses the same Engine API.
    path2 = tmp_path / "cadcraft-check-ui.dxf"
    cadcraft.save_cadcraft_preview_dxf(path2, scene)
    assert [e.dxftype() for e in ezdxf.readfile(path2).modelspace()] == [
        e.dxftype() for e in entities
    ]


def test_cadcraft_gui_module_has_no_dxf_or_manufacturing_geometry():
    gui = getsource(cadcraft)
    assert "import ezdxf" not in gui
    assert "add_drawing_scene_to_dxf" not in gui
    assert "resolve_surface_features(" not in gui
    assert "scene.add_circle(" not in gui
    assert "scene.add_polyline(" not in gui
    assert "project_cadcraft_check_scene(" in gui
    assert "save_cadcraft_check_scene_dxf(" in gui
    engine = (Path(__file__).resolve().parents[1]
              / "ae_engine/operator_cadcraft_preview.py").read_text(encoding="utf-8")
    assert "from gui_modules" not in engine
    assert "tkinter" not in engine
