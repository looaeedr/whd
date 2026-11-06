"""#2517: Box Body true-world mesh eligibility must be Engine-owned."""
from __future__ import annotations

from types import SimpleNamespace
import inspect

import pytest
from ae_engine import manufacturing_api as api, resolve_box_body_formed_width_datum
import phase6_final_scene_projection as gui
from ae_engine.box_body_structure import resolve_box_body_structure
from ae_engine.box_body_structure_state import (
    BoxBodyStructureType, default_box_body_structure_state, set_active_structure,
)
from ae_engine.manufacturing_api import build_box_body_fold_profile


def piece(role, end, start=None, width=None):
    return SimpleNamespace(role=role, formed_w_end=end, formed_w_start=start,
                           formed_outer_width=width)


def test_real_two_piece_box_body_uses_exact_canonical_outside_width():
    snapshot = {
        "w": 1200.0, "h": 1600.0, "d": 400.0, "t": 2.0,
        "fw": 25.0, "zl1": 15.0, "zl2": 20.0,
        "zr1": 15.0, "zr2": 20.0,
    }
    profile = build_box_body_fold_profile(snapshot)
    state = set_active_structure(
        default_box_body_structure_state(), BoxBodyStructureType.TWO_PIECE_W_SPLIT,
    )
    resolved = resolve_box_body_structure(
        profile, w=1200, h=1600, d=400, t=2, structure_state=state,
    )
    assert api.resolve_box_body_formed_width_datum(resolved.pieces) == pytest.approx(1200)
    assert gui._phase6_box_body_formed_width_datum(resolved.pieces) == pytest.approx(1200)


def test_true_receiving_left_side_zero_origin_requires_both_source_anchors():
    pieces = [
        piece("left_side", 0.0, start=0.0, width=350.0),
        piece("back", 795.0, start=0.0, width=795.0),
        piece("right_side", 800.0, start=800.0, width=350.0),
    ]
    assert resolve_box_body_formed_width_datum(pieces) == pytest.approx(800)
    assert gui._phase6_box_body_formed_width_datum(pieces) == 800
    pieces[0] = piece("left_side", 0.0, start=None, width=350.0)
    with pytest.raises(ValueError, match="INCOMPLETE"):
        api.resolve_box_body_formed_width_datum(pieces)


@pytest.mark.parametrize("pieces", [
    [piece("right", False)],
    [piece("right", float("inf"))],
    [piece("right", "not-a-width")],
    [piece("left_side", 0.0, start=1, width=350), piece("right", 800)],
    [piece("middle", 0.0), piece("right", 800)],
    [piece("left_side", 0.0, start=0.0, width=0), piece("right", 800)],
])
def test_invalid_or_incomplete_physical_width_fails_closed(pieces):
    with pytest.raises(ValueError, match="BOX_BODY_PIECE_OUTSIDE_DATUM_"):
        api.resolve_box_body_formed_width_datum(pieces)


def test_only_preview_stubs_are_not_made_into_physical_sheets():
    stubs = [piece("left", 0), piece("right", None)]
    assert api.resolve_box_body_formed_width_datum(stubs) is None
    assert api.resolve_box_body_formed_width_datum([]) is None


def test_phase6_adapter_forwards_without_second_physical_datum_owner(monkeypatch):
    original = api.resolve_box_body_formed_width_datum
    calls = []
    def spy(pieces):
        calls.append(pieces)
        return original(pieces)
    monkeypatch.setattr(api, "resolve_box_body_formed_width_datum", spy)
    rows = [piece("left", 500), piece("right", 800)]
    assert gui._phase6_box_body_formed_width_datum(rows) == 800
    assert calls == [rows]
    source = inspect.getsource(gui._phase6_box_body_formed_width_datum)
    assert "manufacturing_api.resolve_box_body_formed_width_datum" in source
    assert "legitimate_left_side" not in source
    assert "formed_w_end" not in source
