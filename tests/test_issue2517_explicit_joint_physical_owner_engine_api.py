"""#2517: Explicit Joint physical relief ownership and cached source proof are Engine APIs."""
from __future__ import annotations
from copy import deepcopy
import inspect
from types import SimpleNamespace
import pytest
from shapely.geometry import box
from ae_engine import manufacturing_api as api
from ae_engine import assembly_joint as owner
from phase6_manufacturing_geometry import (
    _phase6_box_body_piece_solver_key as gui_piece,
    _phase6_side_wrap_target_corners as gui_wrap,
    _phase6_joint_relief_state_item_matches as gui_match,
)
from tests.test_issue39_divider_relief import _body_part, _snapshot


def test_public_engine_owner_and_gui_forwarding():
    for name, gui_fn in (
        ("resolve_box_body_piece_solver_key", gui_piece),
        ("side_wrap_target_corners", gui_wrap),
        ("joint_relief_state_item_matches", gui_match),
    ):
        assert getattr(api, name) is getattr(owner, name)
        assert f"manufacturing_api.{name}(" in inspect.getsource(gui_fn)
    assert "from phase6_" not in inspect.getsource(owner)


def test_real_receiving_multi_piece_requires_unambiguous_physical_uv_owner():
    body = _body_part(_snapshot())
    assert body.render_data.pieces
    for region, wanted in (
        ("left_mating", "box_body:left_side"),
        ("right_mating", "box_body:right_side"),
        ("rear_panel", "box_body:back"),
    ):
        assert api.resolve_box_body_piece_solver_key(body, region, require_flat_uv=True) == wanted
        assert gui_piece(body, region, require_flat_uv=True) == wanted
    assert api.resolve_box_body_piece_solver_key(body, "UNKNOWN", require_flat_uv=False) == "box_body"
    with pytest.raises(ValueError, match="ambiguous"):
        api.resolve_box_body_piece_solver_key(body, "UNKNOWN", require_flat_uv=True)


def test_side_wrap_targets_are_engine_owned():
    assert api.side_wrap_target_corners("head") == ("top_left", "top_right")
    assert api.side_wrap_target_corners("TAIL") == ("bottom_left", "bottom_right")
    assert gui_wrap("head") == api.side_wrap_target_corners("head")
    with pytest.raises(ValueError, match="head/tail"):
        api.side_wrap_target_corners("side")


def test_saved_cut_source_proof_rejects_stale_or_nonfinite_inputs():
    material = box(0, 0, 10, 20)
    joint = SimpleNamespace(joint_id="joint-1", subject_part="head", target_part="box_body", relation="WRAP")
    source = {
        "joint_id": "joint-1", "subject_part": "head", "target_part": "box_body",
        "relation": "WRAP", "verified": True,
        "source_material_bounds": [0.0, 0.0, 10.0, 20.0], "source_material_area": 200.0,
    }
    before = deepcopy(source)
    assert api.joint_relief_state_item_matches(source, joint, material) is True
    assert gui_match(source, joint, material) is True
    assert source == before
    for patch in (
        {"source_material_bounds": [True, 0.0, 10.0, 20.0]},
        {"source_material_bounds": [float("nan"), 0.0, 10.0, 20.0]},
        {"source_material_area": True}, {"source_material_area": float("inf")},
        {"source_material_area": 199.9}, {"joint_id": "stale"}, {"verified": False},
    ):
        broken = dict(source, **patch)
        assert api.joint_relief_state_item_matches(broken, joint, material) is False
        assert gui_match(broken, joint, material) is False
