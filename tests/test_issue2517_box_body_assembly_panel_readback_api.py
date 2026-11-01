"""#2517: Assembly BoxBody physical-piece panel reads Engine source, not GUI formulas."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.operator_box_body_2d import (
    BoxBodyAssemblyPanelPiece, project_box_body_assembly_panel_piece_rows,
)
from phase6_assembly_presentation import project_box_body_piece_rows
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _test_piece(role, *, key="ignored-source-key", dims=(101, 201), flat=(111, 211)):
    render = object()
    return SimpleNamespace(
        role=role, key=key, formed_outer_dimensions=dims,
        material_dimensions=flat, render_data=render,
    )


def test_headless_source_dimensions_and_legacy_key_fallback_are_immutable():
    pieces = (_test_piece("left_side"), _test_piece("", key="box_body:legacy_piece"))
    payload = SimpleNamespace(pieces=pieces)
    old = deepcopy(payload)
    rows = manufacturing_api.project_box_body_assembly_panel_piece_rows(payload)
    assert manufacturing_api.project_box_body_assembly_panel_piece_rows is (
        project_box_body_assembly_panel_piece_rows
    )
    assert rows == (
        BoxBodyAssemblyPanelPiece(
            "box_body:left_side", 101.0, 201.0, 111.0, 211.0,
            pieces[0].render_data,
        ),
        BoxBodyAssemblyPanelPiece(
            "box_body:legacy_piece", 101.0, 201.0, 111.0, 211.0,
            pieces[1].render_data,
        ),
    )
    assert payload.pieces[0].formed_outer_dimensions == old.pieces[0].formed_outer_dimensions
    assert payload.pieces[1].material_dimensions == old.pieces[1].material_dimensions
    with pytest.raises(FrozenInstanceError):
        rows[0].formed_width = -1


def test_presentation_only_adds_operator_label_and_keeps_engine_source(monkeypatch):
    source = BoxBodyAssemblyPanelPiece(
        "box_body:left_side", 101, 201, 111, 211, object(),
    )
    marker = object()
    calls = []

    def engine(data):
        calls.append(data)
        return (source,)

    monkeypatch.setattr(
        manufacturing_api, "project_box_body_assembly_panel_piece_rows", engine,
    )
    rows = project_box_body_piece_rows(
        marker, label_for=lambda key: "文字:" + key,
    )
    assert calls == [marker]
    assert [(row.part_key, row.label, row.formed_width, row.blank_height) for row in rows] == [
        ("box_body:left_side", "文字:box_body:left_side", 101, 211),
    ]
    assert rows[0].source_render_data is source.source_render_data


def test_real_receiving_box_body_panel_matches_canonical_physical_source():
    source, geometry = _actual(_two_tier)
    body = geometry.part("box_body").render_data
    rows = manufacturing_api.project_box_body_assembly_panel_piece_rows(body)
    assert len(rows) == len(body.pieces) and len(rows) >= 2
    for row, piece in zip(rows, body.pieces):
        assert row.part_key == f"box_body:{piece.role}"
        assert (row.formed_width, row.formed_height) == tuple(
            float(v) for v in piece.formed_outer_dimensions
        )
        assert (row.blank_width, row.blank_height) == tuple(
            float(v) for v in piece.material_dimensions
        )
        assert row.source_render_data is piece.render_data
    present = project_box_body_piece_rows(body, label_for=str)
    assert tuple(p.part_key for p in present) == tuple(p.part_key for p in rows)
    assert tuple(p.source_render_data for p in present) == tuple(
        p.source_render_data for p in rows
    )


def test_panel_reads_engine_corner_source_without_local_piece_role_reconstruction():
    root = Path(__file__).resolve().parents[1]
    panel = (root / "phase6_assembly_panel.py").read_text(encoding="utf-8")
    start = panel.index("def refresh_box_body_piece_info(")
    end = panel.index("def set_corner_texts(", start)
    source = panel[start:end]
    assert "project_box_body_piece_rows(render_data, label_for=label_for)" in source
    assert "projection.source_render_data" in source
    assert "piece_by_role" not in source
    assert "getattr(render_data, \"pieces\"" not in source


def test_missing_or_invalid_manufacturing_dimensions_do_not_create_fake_display():
    assert manufacturing_api.project_box_body_assembly_panel_piece_rows(
        SimpleNamespace(pieces=()),
    ) == ()
    broken = _test_piece("left_side", dims=("bad", 20))
    with pytest.raises(ValueError):
        manufacturing_api.project_box_body_assembly_panel_piece_rows(
            SimpleNamespace(pieces=(broken,)),
        )
