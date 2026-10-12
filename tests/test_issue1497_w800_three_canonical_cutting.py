# -*- coding: utf-8 -*-
"""#1497: W800x3 validated geometry actually becomes 3/6 unique CUTTING holes."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import ezdxf
import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.manufacturing_api import build_inner_door_panel_render_data
from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_cutting_preflight import NfbExistingCuttingClaim
from ae_engine.receiving_nfb_w800_three_cutting import (
    NfbW800ThreeRow,
    configured_w800_three_nfb_inner_door_render_data,
    save_w800_three_nfb_inner_door_dxf,
)
from ae_engine.sheetmetal_drawing import PolylinePrimitive


def _state(left_neighbor=None):
    width = 800.0 + (left_neighbor or 0)
    state = apply_family_defaults({
        "model": "受電箱", "w": width, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    })
    columns = ([[800.0, [1100.0, 500.0]]] if left_neighbor is None
               else [[left_neighbor, [1100.0, 500.0]],
                     [800.0, [1100.0, 500.0]]])
    state.update({
        "w": width, "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": columns,
        "inner_doors": [{
            "stable_id": "upper",
            "cell_key": "0:0" if left_neighbor is None else "1:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    })
    return state


def _source(tmp_path):
    # Exact production brand+DXF name is resolved against real operator CSV.
    # Synthetic bytes here test physics independently of optional original
    # replay; a supplied unrecognized SHA cannot pass production validation.
    index = Path(__file__).resolve().parents[1] / (
        "基準檔/開孔/NFB/開關索引.csv"
    )
    original = tmp_path / "400_140X257_107.dxf"
    drawing = ezdxf.new("R2010")
    upper = drawing.modelspace().add_lwpolyline(
        [(0.0, 0.0), (57.0, 0.0), (57.0, 96.0), (0.0, 96.0)],
        close=True, dxfattribs={"color": 150},
    )
    drawing.saveas(original)
    profile = NfbUpperSourceProfile(
        brand="士林", indexed_filename=original.name,
        source_sha256=sha256(original.read_bytes()).hexdigest(),
        upper_handle=str(upper.dxf.handle), upper_size_mm=(57.0, 96.0),
        source_alias_status="SOURCE_OBSERVED_UNCERTIFIED",
        revision="WHD-1497-SYNTHETIC-REGRESSION-ONLY",
    )
    return index, original, profile


def _row(layer_index=0, *, angles=(0, 0, 0)):
    return NfbW800ThreeRow(
        layer_index=layer_index,
        physical_hole_ids=tuple(
            f"nfb:upper:layer:{layer_index}:horizontal:{j}" for j in range(3)
        ),
        rotations_deg=angles,
    )


def _actual_cuttings(verified):
    return [
        p for p in verified.render_data.scene.primitives
        if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING" and p.closed
    ]


@pytest.mark.parametrize("neighbor,expected_world", [
    (None, (-180.0, 0.0, 180.0)),
    (400.0, (20.0, 200.0, 380.0)),
])
def test_w800x3_uses_whd_723_blank_x_for_three_real_holes(
    tmp_path, neighbor, expected_world,
):
    state = _state(neighbor)
    before = deepcopy(state)
    index, source, profile = _source(tmp_path)
    panel = next(p for p in cabinet_family_policy.derive_inner_door_panels(state)
                 if p.inner_door_id == "upper")
    original = build_inner_door_panel_render_data(panel)
    result = configured_w800_three_nfb_inner_door_render_data(
        state, "upper", rows=(_row(angles=(0, 90, 270)),),
        index_path=index, source_path=source, profile=profile,
    )
    assert result.manufacturing_ready
    assert len(result.physical_hole_ids) == 3
    assert [x[1] for x in result.verified_hole_locations] == pytest.approx(expected_world)
    assert [(x[2], x[3], x[4]) for x in result.verified_hole_locations] == [
        (1, 0, 0), (1, 0, 90), (1, 0, 270),
    ]
    contours = _actual_cuttings(result)
    assert len(contours) == 4  # original outer CUTTING + actual 3 NFB holes
    centers = [((min(p.x for p in c.points) + max(p.x for p in c.points))/2,
                (min(p.y for p in c.points) + max(p.y for p in c.points))/2)
               for c in contours[1:]]
    assert [p[0] for p in centers] == pytest.approx((181.5, 361.5, 541.5))
    assert centers[0][1] == pytest.approx(centers[1][1])
    assert centers[1][1] == pytest.approx(centers[2][1])
    measured = [(max(p.x for p in c.points)-min(p.x for p in c.points),
                 max(p.y for p in c.points)-min(p.y for p in c.points))
                for c in contours[1:]]
    for actual, expected in zip(measured, ((57., 96.), (96., 57.), (96., 57.))):
        assert actual == pytest.approx(expected)
    assert build_inner_door_panel_render_data(panel).scene.primitives == (
        original.scene.primitives
    )
    assert state == before


def test_two_configured_layers_six_unique_holes_and_final_saved_dxf(tmp_path):
    index, source, profile = _source(tmp_path)
    dest = tmp_path / "verified-W800x3-twice.dxf"
    state = _state()
    rows = (_row(0), _row(1, angles=(90, 180, 270)))
    result = configured_w800_three_nfb_inner_door_render_data(
        state, "upper", rows=rows,
        index_path=index, source_path=source, profile=profile,
    )
    assert len(result.verified_hole_locations) == 6
    assert len({p[0] for p in result.verified_hole_locations}) == 6
    assert [(p[2], p[3]) for p in result.verified_hole_locations] == [
        (2, 0)]*3 + [(2, 1)]*3
    assert len(_actual_cuttings(result)) == 7
    save_w800_three_nfb_inner_door_dxf(
        state, "upper", dest, rows=rows,
        index_path=index, source_path=source, profile=profile,
    )
    drawing = ezdxf.readfile(dest)
    cuts = [ent for ent in drawing.modelspace()
            if ent.dxftype() == "LWPOLYLINE"
            and ent.dxf.layer == "CUTTING" and ent.closed]
    assert len(cuts) == 7
    assert all(ent.dxf.color == 3 for ent in cuts[1:])


@pytest.mark.parametrize("rows", [
    (), (_row(), _row(0)),
    (_row(1),),
    (_row(), _row(2)),
    (NfbW800ThreeRow(layer_index=0, physical_hole_ids=("one", "two", "two")),),
    (NfbW800ThreeRow(layer_index=0, physical_hole_ids=("one", "two", "three"),
                      rotations_deg=(0, 90, 45)),),
    (NfbW800ThreeRow(layer_index=0, physical_hole_ids=("one", "two")),),
])
def test_w800x3_invalid_config_is_atomic_no_dxf(tmp_path, rows):
    idx, src, profile = _source(tmp_path)
    dest = tmp_path / "must-not-exist.dxf"
    with pytest.raises((ValueError, TypeError)):
        save_w800_three_nfb_inner_door_dxf(
            _state(), "upper", dest, rows=rows,
            index_path=idx, source_path=src, profile=profile,
        )
    assert not dest.exists()


@pytest.mark.parametrize("changed", [
    {"w": 799.0},
    {"t": 3.0},
    {"door_gap_w": 4.0},
    {"multi_door_enabled": False},
])
def test_w800x3_rejects_unproven_part_dimensions(tmp_path, changed):
    idx, src, profile = _source(tmp_path)
    state = _state()
    state.update(changed)
    with pytest.raises(ValueError, match="OPEN-X-W800x3"):
        configured_w800_three_nfb_inner_door_render_data(
            state, "upper", rows=(_row(),),
            index_path=idx, source_path=src, profile=profile,
        )


def test_w800x3_source_sha_and_existing_hole_owner_fail_without_output(tmp_path):
    idx, src, profile = _source(tmp_path)
    dst = tmp_path / "must-not-be-written.dxf"
    kwargs = dict(index_path=idx, source_path=src, rows=(_row(),))
    with pytest.raises(ValueError, match="SHA"):
        save_w800_three_nfb_inner_door_dxf(
            _state(), "upper", dst,
            profile=replace(profile, source_sha256="0" * 64), **kwargs,
        )
    assert not dst.exists()

    old_hole = NfbExistingCuttingClaim(
        physical_hole_id="nfb:upper:layer:0:horizontal:1",
        part_id="inner_door:upper:panel",
        outline_uv_xy=((330., 420.), (394., 420.), (394., 600.), (330., 600.)),
    )
    with pytest.raises(ValueError, match="blocked"):
        save_w800_three_nfb_inner_door_dxf(
            _state(), "upper", dst, profile=profile,
            existing_claims=(old_hole,), **kwargs,
        )
    assert not dst.exists()
