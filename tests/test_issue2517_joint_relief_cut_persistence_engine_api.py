"""#2517: stored verified Joint relief polygons belong to Engine, not GUI."""
from __future__ import annotations

import inspect
import json

import pytest
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Polygon, box

from ae_engine import manufacturing_api as api
from ae_engine import assembly_collision as owner
from phase6_manufacturing_geometry import (
    _phase6_relief_polygon_coords as gui_serialize,
    _phase6_cut_geometry_from_state_item as gui_restore,
)


def test_public_codec_uses_existing_engine_collision_owner_and_phase6_forwards():
    assert api.serialize_joint_relief_polygons is owner.serialize_joint_relief_polygons
    assert api.restore_joint_relief_cut_geometry is owner.restore_joint_relief_cut_geometry
    assert "manufacturing_api.serialize_joint_relief_polygons(" in inspect.getsource(gui_serialize)
    assert "manufacturing_api.restore_joint_relief_cut_geometry(" in inspect.getsource(gui_restore)


def test_two_physical_polygons_are_stable_across_json_save_reload_and_gui_adapter():
    actual_cut = MultiPolygon((box(0, 0, 3, 4), box(10, 10, 12, 15)))
    stored = api.serialize_joint_relief_polygons(actual_cut)
    assert stored == gui_serialize(actual_cut)
    assert len(stored) == 2
    assert all(len(ring) >= 3 and ring[0] != ring[-1] for ring in stored)
    source_item = json.loads(json.dumps({"cut_polygons": stored}, ensure_ascii=False))
    restored = api.restore_joint_relief_cut_geometry(source_item)
    assert restored is not None
    assert restored.equals(actual_cut)
    assert restored.equals(gui_restore(source_item))
    assert float(restored.area) == pytest.approx(float(actual_cut.area))


def test_irrelevant_geometry_and_empty_persisted_data_cannot_forge_cut():
    assert api.serialize_joint_relief_polygons(None) == []
    assert api.restore_joint_relief_cut_geometry(None) is None
    assert api.restore_joint_relief_cut_geometry({"cut_polygons": []}) is None
    mixed = GeometryCollection((box(0, 0, 4, 4), LineString([(0, 0), (1, 1)])))
    assert len(api.serialize_joint_relief_polygons(mixed)) == 1
    assert api.serialize_joint_relief_polygons(Polygon()) == []


def test_invalid_saved_polygon_coordinates_fail_without_any_cut():
    for bad in (
        {"cut_polygons": [[["not-a-number", 0], [1, 0], [0, 1]]]},
        {"cut_polygons": [[["1", "2"], ["2", "2"]]]},
        {"cut_polygons": [[[]]]},
    ):
        assert api.restore_joint_relief_cut_geometry(bad) is None
        assert gui_restore(bad) is None
