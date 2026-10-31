"""#2517: real BoxBody physical piece profile readback belongs to Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

from ae_engine import manufacturing_api as api
from ae_engine import box_body_editor_readback as owner
from fold_designer_bridge import (
    _phase6_reverse_fold_traversal as legacy_reverse,
    _phase6_box_body_piece_part_profiles as legacy_projection,
)
from tests.test_issue39_divider_relief import _body_part, _snapshot


def test_engine_owns_reverse_and_physical_piece_readback_without_gui_dependency():
    assert api.reverse_box_body_fold_traversal is owner.reverse_box_body_fold_traversal
    assert api.box_body_piece_editor_profiles is owner.box_body_piece_editor_profiles
    assert "manufacturing_api.reverse_box_body_fold_traversal(" in inspect.getsource(legacy_reverse)
    assert "manufacturing_api.box_body_piece_editor_profiles(" in inspect.getsource(legacy_projection)
    assert "from phase6_" not in inspect.getsource(owner)
    assert "fold_designer_bridge" not in inspect.getsource(owner)


def test_right_side_reverse_preserves_bend_boundary_and_does_not_mutate_source():
    source = [
        {"len": 10.0, "angle": 90.0, "phase6_key": "zl1"},
        {"len": 20.0, "angle": -90.0, "phase6_key": "zl2"},
        {"len": 30.0, "phase6_key": "d_left"},
    ]
    saved = deepcopy(source)
    actual = api.reverse_box_body_fold_traversal(source)
    assert source == saved
    assert actual == legacy_reverse(source)
    assert [row["len"] for row in actual] == [30.0, 20.0, 10.0]
    assert [row.get("angle") for row in actual] == [-90.0, 90.0, None]


def test_real_receiving_physical_left_right_fold_api_and_save_reload_match():
    snapshot = _snapshot()
    body = _body_part(snapshot)
    source = body.render_data
    original_snapshot = deepcopy(snapshot)
    original_roles = tuple((piece.role, piece.fold_profile) for piece in source.pieces)
    projected = api.box_body_piece_editor_profiles(source, snapshot)
    assert projected == legacy_projection(source, snapshot)
    assert snapshot == original_snapshot
    assert tuple((piece.role, piece.fold_profile) for piece in source.pieces) == original_roles
    for key in ("box_body:left_side", "box_body:back", "box_body:right_side"):
        assert key in projected
        assert projected[key]["X"]
        assert projected[key]["Y"]
        assert projected[key]["Y"][0]["len"] > 0
    assert json.loads(json.dumps(projected, ensure_ascii=False)) == projected
    assert projected["box_body:right_side"]["X"][-1].get("angle") is None
    if float(snapshot["zl1"]) < 0:
        assert any(
            row["phase6_key"] == "zl1" and row.get("phase6_ui_sign") == -1.0
            for row in projected["box_body:left_side"]["X"]
        )
