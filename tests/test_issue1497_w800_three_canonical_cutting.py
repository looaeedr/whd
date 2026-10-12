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
from ae_engine.manufacturing_render_data import material_polygon_from_final_scene
from ae_engine.sheetmetal_drawing import DrawingScene, CirclePrimitive
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


def _original_finalscene_with_legacy(panel, *, target_xy, hole_id="legacy:door:1",
                                     kind="CIRCLE"):
    """Actual current final scene: structural panel PLUS existing Feature hole."""
    native = build_inner_door_panel_render_data(panel)
    drawn = DrawingScene()
    drawn.extend(native.scene.primitives)
    if kind == "CIRCLE":
        drawn.add_circle(target_xy, 6., layer="CUTTING", color=3,
                         source_id=hole_id)
    elif kind == "POLYLINE":
        x,y=target_xy
        drawn.add_polyline((
            (x-4.,y-4.),(x+4.,y-4.),(x+4.,y+4.),(x-4.,y+4.)
        ),layer="CUTTING",closed=True,color=3)
    elif kind == "OPEN_CUTTING":
        x,y=target_xy
        drawn.add_line((x-4.,y),(x+4.,y),layer="CUTTING",color=3)
    else:
        raise ValueError("invalid fixture kind")
    drawn.add_line((20.,20.),(30.,20.),layer="MARKING",color=212)
    return replace(native,scene=drawn,material=material_polygon_from_final_scene(drawn))


def test_existing_legacy_circle_is_preserved_exactly_once_in_real_nfb_dxf(tmp_path):
    state=_state()
    idx,src,profile=_source(tmp_path)
    panel=next(p for p in cabinet_family_policy.derive_inner_door_panels(state)
               if p.inner_door_id=="upper")
    legacy=_original_finalscene_with_legacy(
        panel,target_xy=(76.,130.),hole_id="legacy:door:bolt:42",
    )
    before=tuple(legacy.scene.primitives)
    ready=configured_w800_three_nfb_inner_door_render_data(
        state,"upper",rows=(_row(),),index_path=idx,
        source_path=src,profile=profile,existing_render_data=legacy,
    )
    assert ready.manufacturing_ready
    assert tuple(ready.render_data.scene.primitives[:len(before)])==before
    assert sum(isinstance(p,CirclePrimitive) and p.source_id=="legacy:door:bolt:42"
               for p in ready.render_data.scene.primitives)==1
    assert len(_actual_cuttings(ready))==4
    assert tuple(legacy.scene.primitives)==before

    path=tmp_path/"door-with-existing-legacy-and-three-nfb.dxf"
    save_w800_three_nfb_inner_door_dxf(
        state,"upper",path,rows=(_row(),),index_path=idx,
        source_path=src,profile=profile,existing_render_data=legacy,
    )
    native=ezdxf.readfile(path).modelspace()
    assert len([e for e in native if e.dxftype()=="CIRCLE"
                and e.dxf.layer=="CUTTING"])==1
    assert len([e for e in native if e.dxftype()=="LWPOLYLINE"
                and e.dxf.layer=="CUTTING" and e.closed])==4


def test_legacy_polyline_and_marking_survive_noncolliding_nfb(tmp_path):
    state=_state()
    idx,src,profile=_source(tmp_path)
    panel=next(p for p in cabinet_family_policy.derive_inner_door_panels(state)
               if p.inner_door_id=="upper")
    legacy=_original_finalscene_with_legacy(
        panel,target_xy=(77.,180.),kind="POLYLINE",
    )
    result=configured_w800_three_nfb_inner_door_render_data(
        state,"upper",rows=(_row(),),
        index_path=idx,source_path=src,profile=profile,
        existing_render_data=legacy,
    )
    assert len(_actual_cuttings(result))==5
    assert tuple(result.render_data.scene.primitives[:len(legacy.scene.primitives)])==(
        tuple(legacy.scene.primitives)
    )


def test_legacy_same_location_or_same_physical_owner_blocks_atomic_export(tmp_path):
    state=_state()
    idx,src,profile=_source(tmp_path)
    panel=next(p for p in cabinet_family_policy.derive_inner_door_panels(state)
               if p.inner_door_id=="upper")
    reference=configured_w800_three_nfb_inner_door_render_data(
        state,"upper",rows=(_row(),),
        index_path=idx,source_path=src,profile=profile,
    )
    proposed=_actual_cuttings(reference)[2]  # center of second new hole
    xs=[p.x for p in proposed.points]
    ys=[p.y for p in proposed.points]
    same_spot=(sum((min(xs),max(xs)))/2.,sum((min(ys),max(ys)))/2.)
    for center,legacy_id in (
        (same_spot,"legacy:different-physical-id"),
        ((76.,130.),_row().physical_hole_ids[0]),
    ):
        existing=_original_finalscene_with_legacy(
            panel,target_xy=center,hole_id=legacy_id,
        )
        output=tmp_path/"must-not-write-after-legacy-collision.dxf"
        with pytest.raises(ValueError,match="blocked"):
            save_w800_three_nfb_inner_door_dxf(
                state,"upper",output,rows=(_row(),),
                index_path=idx,source_path=src,profile=profile,
                existing_render_data=existing,
            )
        assert not output.exists()


@pytest.mark.parametrize("change", ["foreign_part","stale_topology",
                                    "altered_structural_outer","open_legacy_cutting"])
def test_bad_or_unresolved_existing_legacy_finalscene_never_writes(tmp_path,change):
    state=_state()
    idx,src,profile=_source(tmp_path)
    panel=next(p for p in cabinet_family_policy.derive_inner_door_panels(state)
               if p.inner_door_id=="upper")
    legacy=_original_finalscene_with_legacy(
        panel,target_xy=(76.,130.),
        kind="OPEN_CUTTING" if change=="open_legacy_cutting" else "CIRCLE",
    )
    if change=="foreign_part":
        legacy=replace(legacy,metadata={**legacy.metadata,"stable_id":"other:panel"})
    elif change=="stale_topology":
        legacy=replace(legacy,unfolded_topology=None)
    elif change=="altered_structural_outer":
        revised=DrawingScene()
        revised.extend(tuple(legacy.scene.primitives)[1:])
        legacy=replace(legacy,scene=revised)
    output=tmp_path/"invalid-existing-source.dxf"
    with pytest.raises(ValueError,match="NFB legacy|NFB existing"):
        save_w800_three_nfb_inner_door_dxf(
            state,"upper",output,rows=(_row(),),
            index_path=idx,source_path=src,profile=profile,
            existing_render_data=legacy,
        )
    assert not output.exists()
