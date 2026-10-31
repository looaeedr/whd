"""#2517: Joint Solver's real world/UV collision mesh is an Engine API."""
from __future__ import annotations
from copy import deepcopy
import inspect

from ae_engine import build_joint_world_geometry, manufacturing_api as api
from ae_engine import assembly_geometry as owner
from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry as gui_world
from tests.test_piece_level_joint_geometry import _receiving_body_part
from tests.test_issue39_divider_relief import _snapshot, _body_part, _divider_part


def test_only_engine_builds_joint_mesh_and_phase6_is_compat_adapter():
    assert api.build_joint_world_geometry is owner.build_joint_world_geometry
    assert build_joint_world_geometry is api.build_joint_world_geometry
    assert "manufacturing_api.build_joint_world_geometry(" in inspect.getsource(gui_world)
    engine_source = inspect.getsource(owner.build_joint_world_geometry)
    assert "from phase6_" not in engine_source
    assert "expand_box_body_fw_world_mid(" in engine_source
    assert "fit_receiving_left_zl1_world_mid(" in engine_source


def test_true_receiving_split_boxbody_has_separate_physical_uv_and_aggregate_solid():
    body = _receiving_body_part()
    parts = (body,)
    dims = (800.0, 600.0, 350.0)
    engine = api.build_joint_world_geometry(parts, dims, 2.0)
    gui = gui_world(parts, dims, 2.0)
    required = {"box_body:left_side", "box_body:back", "box_body:right_side"}
    assert required.issubset(engine["flat_material_by_part"])
    assert required.issubset(engine["mapped_skin_triangles_by_part"])
    assert required.issubset(engine["world_triangles_by_part"])
    assert "box_body" in engine["world_triangles_by_part"]
    assert "box_body" not in engine["flat_material_by_part"]
    assert "box_body" not in engine["mapped_skin_triangles_by_part"]
    assert len(engine["world_triangles_by_part"]["box_body"]) == sum(
        len(engine["world_triangles_by_part"][k]) for k in required
    )
    assert engine["world_triangles_by_part"] == gui["world_triangles_by_part"]
    assert engine["mapped_skin_triangles_by_part"] == gui["mapped_skin_triangles_by_part"]
    for key in required:
        assert engine["flat_material_by_part"][key].equals(gui["flat_material_by_part"][key])


def test_real_receiving_divider_and_boxbody_use_same_engine_assembly_world_without_mutation():
    snapshot = _snapshot()
    body = _body_part(snapshot)
    _, divider = _divider_part(snapshot)
    before = deepcopy(snapshot)
    parts = (body, divider)
    dims = (snapshot["w"], snapshot["h"], snapshot["d"])
    world = api.build_joint_world_geometry(parts, dims, snapshot["t"])
    assert snapshot == before
    assert divider.part_key in world["world_triangles_by_part"]
    assert divider.part_key in world["mapped_skin_triangles_by_part"]
    assert world["world_triangles_by_part"][divider.part_key]
    assert world["mapped_skin_triangles_by_part"][divider.part_key]
    assert world["world_triangles_by_part"] == gui_world(parts, dims, snapshot["t"])["world_triangles_by_part"]
