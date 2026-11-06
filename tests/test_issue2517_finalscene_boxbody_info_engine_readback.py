# -*- coding: utf-8 -*-
"""#2517 FinalScene BoxBody dimension text must use canonical Engine material source."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

from ae_engine import manufacturing_api
from ae_engine.operator_box_body_2d import BoxBodyAssemblyPanelPiece
from phase6_final_scene_projection import (
    _phase6_box_body_piece_dimension_lines, format_operator_info_text,
)
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def test_gui_formats_engine_physical_readback_without_touching_material(monkeypatch):
    marker = object()
    calls = []
    actual = (
        BoxBodyAssemblyPanelPiece(
            "box_body:left_side", 242.0, 511.5, 239.5, 509.0, None,
        ),
        BoxBodyAssemblyPanelPiece(
            "box_body:back", 400.0, 500.0, 400.0, 500.0, None,
        ),
        BoxBodyAssemblyPanelPiece(
            "box_body:legacy_piece", 10.0, 20.0, 30.0, 40.0, None,
        ),
    )
    def engine(data):
        calls.append(data)
        return actual
    monkeypatch.setattr(
        manufacturing_api, "project_box_body_assembly_panel_piece_rows", engine,
    )
    rows = _phase6_box_body_piece_dimension_lines(marker)
    assert calls == [marker]
    assert rows == (
        "左側板：成形 242 × 511.5 mm；展開 239.5 × 509 mm",
        "後面板：成形 400 × 500 mm；展開 400 × 500 mm",
        "箱身板件：成形 10 × 20 mm；展開 30 × 40 mm",
    )
    request = SimpleNamespace(
        part_key="box_body", render_data=marker,
        finished_dimensions=(800, 1600, 350),
        x_profile=(), y_profile=(), corner_dimension_text="",
        unfolded_blank_text="",
    )
    text = format_operator_info_text(request)
    assert "折後包外：W 800 × H 1600 × D 350 mm" in text
    assert all(row in text for row in rows)


def test_real_receiving_boxbody_dimension_text_matches_same_engine_inventory():
    source, geometry = _actual(_two_tier)
    render = geometry.part("box_body").render_data
    before = tuple(
        (str(piece.role), tuple(piece.formed_outer_dimensions),
         tuple(piece.material_dimensions), piece.render_data)
        for piece in render.pieces
    )
    engine_rows = manufacturing_api.project_box_body_assembly_panel_piece_rows(
        render,
    )
    texts = _phase6_box_body_piece_dimension_lines(render)
    assert len(texts) == len(engine_rows) == len(render.pieces)
    labels = {
        "left_side": "左側板", "back": "後面板",
        "right_side": "右側板",
    }
    for text, row in zip(texts, engine_rows):
        role = row.part_key.split(":", 1)[1]
        assert text.startswith(labels.get(role, "箱身板件") + "：成形 ")
        assert "；展開 " in text and text.endswith(" mm")
    after = tuple(
        (str(piece.role), tuple(piece.formed_outer_dimensions),
         tuple(piece.material_dimensions), piece.render_data)
        for piece in render.pieces
    )
    assert all(a[:3] == b[:3] and a[3] is b[3]
               for a, b in zip(before, after))
    assert _phase6_box_body_piece_dimension_lines(SimpleNamespace(pieces=())) == ()


def test_finalscene_text_has_no_duplicate_physical_piece_identity_or_dimension_math():
    source = inspect.getsource(_phase6_box_body_piece_dimension_lines)
    assert "manufacturing_api.project_box_body_assembly_panel_piece_rows(" in source
    assert 'getattr(render_data, "pieces"' not in source
    assert "piece.formed_outer_dimensions" not in source
    assert "piece.material_dimensions" not in source
    assert "float(" not in source
