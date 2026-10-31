"""#2517: real BoxBody physical side-skin collision transforms live in Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import assembly_geometry_folded_mesh as owner
from phase6_manufacturing_geometry import (
    _phase6_expand_box_body_fw_world_mid as gui_expand,
    _phase6_shift_multistage_terminal_fold_world_mid as gui_shift,
    _phase6_fit_receiving_left_zl1_outside_world_mid as gui_fit,
    _phase6_build_joint_world_geometry,
)
from tests.test_issue39_divider_relief import _body_part, _snapshot


def test_public_engine_skin_transforms_are_original_solver_owner():
    for engine_name, gui_fn in (
        ("expand_box_body_fw_world_mid", gui_expand),
        ("shift_multistage_terminal_fold_world_mid", gui_shift),
        ("fit_receiving_left_zl1_world_mid", gui_fit),
    ):
        assert getattr(api, engine_name) is getattr(owner, engine_name)
        assert f"manufacturing_api.{engine_name}(" in inspect.getsource(gui_fn)
    assert "from phase6_" not in inspect.getsource(owner)


def test_right_left_transform_preserves_flat_skin_when_no_fw_or_no_multistage():
    piece = SimpleNamespace(role="back", fold_profile=())
    triangles = (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)
    before = deepcopy(triangles)
    assert api.expand_box_body_fw_world_mid(piece, (), triangles, sheet_thickness=2.0) == before
    assert api.shift_multistage_terminal_fold_world_mid(piece, (), triangles) == before
    assert api.fit_receiving_left_zl1_world_mid(piece, (), triangles, sheet_thickness=2.0) == before


def test_true_receiving_side_world_skin_matches_same_source_fixture_and_remains_read_only():
    snapshot = _snapshot()
    body = _body_part(snapshot)
    before = deepcopy(snapshot)
    solved = _phase6_build_joint_world_geometry(
        (body,), (snapshot["w"], snapshot["h"], snapshot["d"]), snapshot["t"],
    )
    rows = solved["mapped_skin_triangles_by_part"]
    assert "box_body:left_side" in rows
    assert "box_body:right_side" in rows
    assert rows["box_body:left_side"]
    assert rows["box_body:right_side"]
    assert snapshot == before


def test_receiving_left_invalid_mapped_mesh_fails_closed_in_engine_and_gui():
    source = _snapshot()
    body = _body_part(source)
    piece = next(p for p in body.render_data.pieces if p.role == "left_side")
    # The real physical zl1 needs the complete UV/mesh map. An invented single
    # triangle is NOT a valid manufacturing input or an authorized expected skin.
    invalid = (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)
    for resolve in (api.fit_receiving_left_zl1_world_mid, gui_fit):
        with pytest.raises(ValueError, match="RECEIVING_ZL1_MAPPED_MESH_MISMATCH"):
            resolve(piece, (), invalid, sheet_thickness=source["t"])
