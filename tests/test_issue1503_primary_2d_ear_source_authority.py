# -*- coding: utf-8 -*-
"""#1503 primary 2D SIDE MARKING must read committed FoldDesigner, not stale main mirror."""
from types import SimpleNamespace

import pytest

from gui_modules.application.receiving_ear_side_2d import (
    present_receiving_ear_side_piece_2d,
)
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _piece(geometry, role):
    return next(p for p in geometry.part("box_body").render_data.pieces
                if p.role == role)


@pytest.mark.parametrize("side", ("left_side", "right_side"))
def test_primary_side_2d_uses_committed_designer_when_main_mirror_has_no_nfb(side):
    committed, geometry = _actual(_two_tier)
    mirror = {key: value for key, value in committed.items()
              if key not in ("nfb_config_submitted", "nfb_config")}
    source = _piece(geometry, side)
    calls = []
    designer = SimpleNamespace(
        _phase6_input_snapshot=committed,
        _phase6_resolve_manufacturing_geometry=lambda: calls.append("real_designer_geometry") or geometry,
    )
    host = SimpleNamespace(
        fold_designer_app=designer,
        _compose_phase6_project_snapshot_from_main_gui=lambda: mirror,
    )
    shown, blocker = present_receiving_ear_side_piece_2d(
        host, geometry.part("box_body").render_data, source, f"box_body:{side}",
    )
    assert blocker is None, blocker
    assert calls == ["real_designer_geometry"]
    assert shown is not source
    assert shown.render_data.metadata["ear_side_mark_preview_owner"] == f"box_body:{side}"
    assert shown.render_data.metadata["ear_side_mark_preview_count"] == 8
    assert shown.render_data.metadata["ear_side_mark_preview_only"] is True
    actual = [r for r in shown.render_data.scene.primitives
              if getattr(r, "layer", "").upper() == "MARKING"]
    assert len(actual) >= 8
    assert tuple(source.render_data.scene.primitives) == tuple(
        _piece(geometry, side).render_data.scene.primitives
    ), "2D display must not modify source material or production DXF"
    cached, cache_blocker = present_receiving_ear_side_piece_2d(
        host, geometry.part("box_body").render_data, source, f"box_body:{side}",
    )
    assert cached is shown and cache_blocker is None
    assert calls == ["real_designer_geometry"]


def test_stale_primary_submitted_flag_cannot_override_unsubmitted_designer():
    committed, geometry = _actual(_two_tier)
    unsubmitted = {**committed, "nfb_config_submitted": False}
    host = SimpleNamespace(
        fold_designer_app=SimpleNamespace(_phase6_input_snapshot=unsubmitted),
        _compose_phase6_project_snapshot_from_main_gui=lambda: committed,
    )
    side = "box_body:left_side"
    piece, blocker = present_receiving_ear_side_piece_2d(
        host, geometry.part("box_body").render_data,
        _piece(geometry, "left_side"), side,
    )
    assert blocker and "EAR_2D_PREVIEW_PRIMARY_SOURCE_DRIFT" in blocker
    assert piece is _piece(geometry, "left_side")


def test_nonreceiving_or_missing_designer_geometry_never_fabricates_marks():
    committed, geometry = _actual(_two_tier)
    source = _piece(geometry, "left_side")
    host = SimpleNamespace(
        fold_designer_app=SimpleNamespace(_phase6_input_snapshot={"model": "金庫型"}),
        _compose_phase6_project_snapshot_from_main_gui=lambda: committed,
    )
    shown, blocker = present_receiving_ear_side_piece_2d(
        host, geometry.part("box_body").render_data, source, "box_body:left_side",
    )
    assert shown is source and blocker is None
