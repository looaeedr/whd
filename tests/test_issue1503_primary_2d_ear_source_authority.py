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
    assert shown.render_data.metadata["ear_side_mark_preview_count"] == 6
    assert shown.render_data.metadata["ear_side_mark_preview_only"] is True
    actual = [r for r in shown.render_data.scene.primitives
              if getattr(r, "layer", "").upper() == "MARKING"]
    assert len(actual) >= 6
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


@pytest.mark.parametrize("side,expected_marks", (
    ("left_side", 6), ("right_side", 6),
))
def test_actual_primary_boxbody_2d_panel_must_use_same_designer_side_material(side, expected_marks):
    from gui_modules.application.render_snapshots import box_body_render_snapshot
    committed, geometry = _actual(_two_tier)
    mirror = {key: value for key, value in committed.items()
              if key not in ("nfb_config_submitted", "nfb_config")}
    calls = []
    designer = SimpleNamespace(
        _phase6_input_snapshot=committed,
        _phase6_resolve_manufacturing_geometry=(
            lambda: calls.append("designer_geometry") or geometry
        ),
    )
    def reject_generic(*args, **kwargs):
        raise AssertionError("PRIMARY_OLD_GENERIC_BOXBODY_MUST_NOT_BE_BUILT")
    host = SimpleNamespace(
        fold_designer_app=designer,
        _compose_phase6_project_snapshot_from_main_gui=lambda: mirror,
        _box_body_part_spec=reject_generic,
        _authoritative_render_data=reject_generic,
        _refresh_box_body_piece_tabs_2d=lambda real: f"box_body:{side}",
    )
    view = box_body_render_snapshot(
        host, {"model": "受電箱", "w": 800., "h": 1600., "d": 350.},
    )
    assert view["mode"] == "piece"
    assert view["piece_key"] == f"box_body:{side}"
    assert view["ear_marking_preview_blocker"] is None
    assert view["render_data"] is geometry.part("box_body").render_data
    assert view["piece"].render_data.metadata["ear_side_mark_preview_count"] == expected_marks
    assert calls == ["designer_geometry", "designer_geometry"]
    assert not hasattr(host, "_legacy_preview_render_cache")
