"""#2517 BoxBody 2D physical current source and role identity only in Engine."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.operator_box_body_2d import (
    project_box_body_2d_piece_inventory,
    project_receiving_box_body_2d_source,
)
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def test_actual_committed_receiving_side_source_is_exact_engine_part_without_copy():
    source, geometry = _actual(_two_tier)
    real = geometry.part("box_body").render_data
    assert manufacturing_api.project_receiving_box_body_2d_source(geometry) is real
    assert manufacturing_api.project_receiving_box_body_2d_source is project_receiving_box_body_2d_source
    keys, left = manufacturing_api.project_box_body_2d_piece_inventory(
        real, "box_body:left_side",
    )
    assert "box_body:left_side" in keys
    assert "box_body:right_side" in keys
    assert left is next(p for p in real.pieces if p.role == "left_side")
    assert manufacturing_api.project_box_body_2d_piece_inventory is project_box_body_2d_piece_inventory
    assert left.render_data.material is not None


def test_only_existing_engine_piece_can_be_selected_and_aggregate_uses_real_source():
    left = SimpleNamespace(role="left_side")
    back = SimpleNamespace(role="back")
    data = SimpleNamespace(pieces=(left, back))
    assert project_box_body_2d_piece_inventory(data, "box_body:left_side") == (
        ("box_body:left_side", "box_body:back"), left,
    )
    assert project_box_body_2d_piece_inventory(data, "box_body:missing")[1] is None
    assert project_box_body_2d_piece_inventory(data, None)[1] is None
    with pytest.raises(IndexError):
        project_box_body_2d_piece_inventory(data, "not-a-part")


def test_missing_current_receiving_boxbody_parts_fail_closed():
    geometry = SimpleNamespace(part=lambda key: SimpleNamespace(
        render_data=SimpleNamespace(pieces=()),
    ))
    with pytest.raises(ValueError, match="缺少現行物理板件"):
        project_receiving_box_body_2d_source(geometry)


def test_gui_only_selects_operator_tab_and_delegates_part_authority():
    source = Path("gui_modules/application/render_snapshots.py").read_text(encoding="utf-8")
    piece_path = source.index("def box_body_render_snapshot(")
    piece_end = source.index("def end_cap_render_snapshot(", piece_path)
    body = source[piece_path:piece_end]
    assert "manufacturing_api.project_receiving_box_body_2d_source(" in body
    assert "manufacturing_api.project_box_body_2d_piece_inventory(" in body
    assert "present_receiving_ear_side_piece_2d(" in body
    for forbidden in ('selected_role =', 'f"box_body:{str(piece.role)}"',
                      'box_body = geometry.part("box_body")'):
        assert forbidden not in body
