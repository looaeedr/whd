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
from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, FeatureAnchor,
)
from ae_engine.receiving_nfb_legacy_feature_bridge import (
    existing_inner_door_feature_finalscene,
)
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_dxf_source import inspect_nfb_dxf_source
from ae_engine.receiving_nfb_part_readiness import (
    NfbPhysicalScope, READY, BLOCKED, LEGACY,
)
from ae_engine.receiving_nfb_capability_matrix import (
    derive_w800_three_nfb_capability, CAPABILITY_SCHEMA,
    CAPABILITY_RULE_REVISION,
)
from ae_engine.receiving_nfb_x_projection import W800_THREE_DATUM_REVISION
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


def test_current_hole_editor_inner_door_feature_auto_projects_and_survives_dxf(tmp_path):
    state=_state()
    original=deepcopy(state)
    idx,src,profile=_source(tmp_path)
    state["part_features"]={
        "inner_door:upper:panel":[
            CircleFeature(
                diameter=12.,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                offset=Vec2(60.,120.),layer="CUTTING",
            ),
            RectFeature(
                width=18.,height=9.,
                anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                offset=Vec2(100.,160.),layer="MARKING",
            ),
        ],
        # This is the OUTER door's Hole Editor store, not the inner panel.
        "door_c1_r1":[
            CircleFeature(
                diameter=22.,anchor=FeatureAnchor.PANEL_CENTER,
                offset=Vec2(0.,0.),layer="CUTTING",
            )
        ],
    }
    before=deepcopy(state)
    ready=configured_w800_three_nfb_inner_door_render_data(
        state,"upper",rows=(_row(),),
        index_path=idx,source_path=src,profile=profile,
    )
    assert ready.manufacturing_ready
    assert ready.render_data.metadata["nfb_legacy_feature_owner"]==(
        "inner_door:upper:panel"
    )
    assert ready.render_data.metadata["nfb_legacy_feature_count"]==2
    native_circles=[
        p for p in ready.render_data.scene.primitives
        if isinstance(p,CirclePrimitive) and p.layer=="CUTTING"
    ]
    assert len(native_circles)==1
    assert (native_circles[0].center.x,
            native_circles[0].center.y)==pytest.approx((77.,137.))
    assert native_circles[0].radius==pytest.approx(6.)
    cuts=_actual_cuttings(ready)
    assert len(cuts)==4
    assert any(p.layer=="MARKING"
               for p in ready.render_data.scene.primitives)
    assert state==before and original!=state

    output=tmp_path/"WHD-existing-HoleEditor-and-three-NFB.dxf"
    save_w800_three_nfb_inner_door_dxf(
        state,"upper",output,rows=(_row(),),
        index_path=idx,source_path=src,profile=profile,
    )
    dxf=ezdxf.readfile(output).modelspace()
    circle=[e for e in dxf if e.dxftype()=="CIRCLE" and e.dxf.layer=="CUTTING"]
    assert len(circle)==1
    assert tuple(circle[0].dxf.center)[:2]==pytest.approx((77.,137.))
    assert len([e for e in dxf
                if e.dxftype()=="LWPOLYLINE"
                and e.dxf.layer=="CUTTING" and e.closed])==4
    assert state==before


def test_true_hole_editor_overlap_blocks_nfb_before_save(tmp_path):
    state=_state()
    idx,src,profile=_source(tmp_path)
    candidate=configured_w800_three_nfb_inner_door_render_data(
        state,"upper",rows=(_row(),),
        index_path=idx,source_path=src,profile=profile,
    )
    contour=_actual_cuttings(candidate)[1]
    x=sum((min(p.x for p in contour.points),
           max(p.x for p in contour.points)))/2.
    y=sum((min(p.y for p in contour.points),
           max(p.y for p in contour.points)))/2.
    panel=next(p for p in cabinet_family_policy.derive_inner_door_panels(state)
               if p.inner_door_id=="upper")
    state["part_features"]={
        panel.stable_id:[CircleFeature(
            diameter=12.,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(x-panel.fold_left+panel.thickness,
                        y-panel.fold_bottom+panel.thickness),
            layer="CUTTING",
        )],
    }
    output=tmp_path/"collision-fails-no-output.dxf"
    before=deepcopy(state)
    with pytest.raises(ValueError,match="blocked"):
        save_w800_three_nfb_inner_door_dxf(
            state,"upper",output,rows=(_row(),),
            index_path=idx,source_path=src,profile=profile,
        )
    assert not output.exists()
    assert state==before


@pytest.mark.parametrize("kind", [
    "unsupported_feature", "out_of_core", "two_owners", "ambiguous_face_map",
])
def test_legacy_inner_door_feature_conflict_never_silently_drops_a_hole(
    tmp_path,kind,
):
    idx,src,profile=_source(tmp_path)
    state=_state()
    circle=CircleFeature(
        diameter=10.,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(60.,120.),layer="CUTTING",
    )
    state["part_features"]={"inner_door:upper:panel":[circle]}
    if kind=="unsupported_feature":
        state["part_features"]["inner_door:upper:panel"]=[{"circle_diameter":10}]
    elif kind=="out_of_core":
        state["part_features"]["inner_door:upper:panel"]=[
            replace(circle,offset=Vec2(2.,5.)),
        ]
    elif kind=="two_owners":
        state["surface_features"]={"inner_door:upper:panel":[circle]}
    elif kind=="ambiguous_face_map":
        state["part_face_features"]={
            "inner_door:upper:panel":{"front":[circle]},
        }
    output=tmp_path/"must-not-silently-ignore-legacy.dxf"
    with pytest.raises((TypeError,ValueError),match="NFB legacy"):
        save_w800_three_nfb_inner_door_dxf(
            state,"upper",output,rows=(_row(),),
            index_path=idx,source_path=src,profile=profile,
        )
    assert not output.exists()


def test_legacy_feature_matches_supplied_original_part_scene_once(tmp_path):
    state=_state()
    idx,src,profile=_source(tmp_path)
    panel=next(p for p in cabinet_family_policy.derive_inner_door_panels(state)
               if p.inner_door_id=="upper")
    state["surface_features"]={panel.stable_id:[
        CircleFeature(diameter=12.,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                      offset=Vec2(60.,120.),layer="CUTTING"),
    ]}
    existing=_original_finalscene_with_legacy(
        panel,target_xy=(77.,137.),hole_id="legacy:operator:1",
    )
    result=configured_w800_three_nfb_inner_door_render_data(
        state,"upper",rows=(_row(),),index_path=idx,
        source_path=src,profile=profile,existing_render_data=existing,
    )
    assert result.manufacturing_ready
    assert len(_actual_cuttings(result))==4
    assert sum(isinstance(x,CirclePrimitive) and x.source_id=="legacy:operator:1"
               for x in result.render_data.scene.primitives)==1
    changed=deepcopy(state)
    changed["surface_features"][panel.stable_id][0]=replace(
        changed["surface_features"][panel.stable_id][0],
        offset=Vec2(61.,120.),
    )
    with pytest.raises(ValueError,match="uniquely own"):
        configured_w800_three_nfb_inner_door_render_data(
            changed,"upper",rows=(_row(),),index_path=idx,
            source_path=src,profile=profile,existing_render_data=existing,
        )


def test_other_outer_door_feature_store_is_not_inner_door_owner(tmp_path):
    state=_state()
    idx,src,profile=_source(tmp_path)
    feature=CircleFeature(
        diameter=14.,anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(0.,0.),layer="CUTTING",
    )
    state["part_features"]={"door_c1_r1":[feature]}
    result=configured_w800_three_nfb_inner_door_render_data(
        state,"upper",rows=(_row(),),index_path=idx,
        source_path=src,profile=profile,
    )
    assert result.manufacturing_ready
    assert len(_actual_cuttings(result))==4
    assert not any(isinstance(x,CirclePrimitive)
                   for x in result.render_data.scene.primitives)


def _part(state):
    return next(
        p for p in cabinet_family_policy.derive_inner_door_panels(state)
        if p.inner_door_id == "upper"
    )


def _edited_inner_door_state(*features):
    state=_state()
    state["part_features"]={"inner_door:upper:panel":list(features)}
    return state


def test_real_hole_editor_circle_and_rect_are_kept_in_three_nfb_cutting(tmp_path):
    # Hole Editor uses the exact inner_door stable_id, not the outer-door ID.
    circle=CircleFeature(
        diameter=12.,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(60.,100.),layer="CUTTING",
    )
    mark=RectFeature(
        width=9.,height=7.,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(90.,125.),layer="MARKING",
    )
    state=_edited_inner_door_state(circle,mark)
    before=deepcopy(state)
    panel=_part(state)
    legacy=existing_inner_door_feature_finalscene(state,panel)
    assert legacy is not None
    # Finished-face 60,100 with fold19 and thickness2 -> unfolded 77,117.
    found=[p for p in legacy.scene.primitives
           if isinstance(p,CirclePrimitive) and p.layer=="CUTTING"]
    assert len(found)==1
    assert (found[0].center.x, found[0].center.y)==pytest.approx((77.,117.))
    mark_rows=[p for p in legacy.scene.primitives
               if isinstance(p,PolylinePrimitive) and p.layer=="MARKING"]
    assert len(mark_rows)==1
    assert legacy.metadata["nfb_legacy_feature_owner"]==panel.stable_id
    assert legacy.metadata["nfb_legacy_feature_count"]==2

    idx,src,profile=_source(tmp_path)
    actual=configured_w800_three_nfb_inner_door_render_data(
        state,"upper",rows=(_row(),),
        index_path=idx,source_path=src,profile=profile,
    )
    assert actual.manufacturing_ready
    assert tuple(actual.render_data.scene.primitives[:len(legacy.scene.primitives)])==(
        tuple(legacy.scene.primitives)
    )
    assert len(_actual_cuttings(actual))==4
    assert sum(isinstance(p,CirclePrimitive) and p.layer=="CUTTING"
               for p in actual.render_data.scene.primitives)==1
    assert sum(isinstance(p,PolylinePrimitive) and p.layer=="MARKING"
               for p in actual.render_data.scene.primitives)==1
    output=tmp_path/"actual-hole-editor-and-three-nfb.dxf"
    save_w800_three_nfb_inner_door_dxf(
        state,"upper",output,rows=(_row(),),
        index_path=idx,source_path=src,profile=profile,
    )
    entities=list(ezdxf.readfile(output).modelspace())
    assert len([x for x in entities if x.dxf.layer=="CUTTING"
                and x.dxftype()=="CIRCLE"])==1
    assert len([x for x in entities if x.dxf.layer=="CUTTING"
                and x.dxftype()=="LWPOLYLINE" and x.closed])==4
    assert state==before


def test_hole_editor_circle_overlapping_real_nfb_is_blocked_atomically(tmp_path):
    idx,src,profile=_source(tmp_path)
    state=_state()
    without=configured_w800_three_nfb_inner_door_render_data(
        state,"upper",rows=(_row(),),
        index_path=idx,source_path=src,profile=profile,
    )
    hole=_actual_cuttings(without)[1]
    xs=[p.x for p in hole.points];ys=[p.y for p in hole.points]
    uvx=(min(xs)+max(xs))/2.;uvy=(min(ys)+max(ys))/2.
    # Same physical position expressed as genuine finished-face Feature.
    legacy=CircleFeature(
        diameter=6.,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(uvx-17.,uvy-17.),layer="CUTTING",
    )
    state["part_features"]={"inner_door:upper:panel":[legacy]}
    target=tmp_path/"must-not-exist.dxf"
    with pytest.raises(ValueError,match="blocked"):
        save_w800_three_nfb_inner_door_dxf(
            state,"upper",target,rows=(_row(),),
            index_path=idx,source_path=src,profile=profile,
        )
    assert not target.exists()


def test_hole_editor_physical_owner_is_exact_and_unrecognized_store_fail_closed(tmp_path):
    circle=CircleFeature(
        diameter=12.,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(60.,100.),layer="CUTTING",
    )
    state=_state()
    panel=_part(state)
    state["part_features"]={"door_c1_r1":[circle]}
    assert existing_inner_door_feature_finalscene(state,panel) is None
    state["part_features"]["inner_door:upper:panel"]=[circle]
    state["surface_features"]={"inner_door:upper:panel":[circle]}
    with pytest.raises(ValueError,match="competing physical Feature stores"):
        existing_inner_door_feature_finalscene(state,panel)
    state.pop("surface_features")
    state["part_features"]["inner_door:upper:panel"]=[{"type":"circle","x":60}]
    with pytest.raises(ValueError,match="format unsupported"):
        existing_inner_door_feature_finalscene(state,panel)
    state["part_features"]["inner_door:upper:panel"]=[circle]
    state["part_face_features"]={"inner_door:upper:panel":{"front":[circle]}}
    with pytest.raises(ValueError,match="face Feature owner not verified"):
        existing_inner_door_feature_finalscene(state,panel)


def test_legacy_features_and_existing_scene_cannot_disagree(tmp_path):
    circle=CircleFeature(
        diameter=12.,anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(60.,100.),layer="CUTTING",
    )
    state=_edited_inner_door_state(circle)
    panel=_part(state)
    previous=build_inner_door_panel_render_data(panel)
    with pytest.raises(ValueError,match="does not uniquely own"):
        existing_inner_door_feature_finalscene(
            state,panel,existing_render_data=previous,
        )
    claimed=existing_inner_door_feature_finalscene(state,panel)
    verified=existing_inner_door_feature_finalscene(
        state,panel,existing_render_data=claimed,
    )
    assert verified is claimed
    assert len(verified.scene.primitives)==len(claimed.scene.primitives)
    foreign=replace(claimed,metadata={**claimed.metadata,"stable_id":"wrong"})
    with pytest.raises(ValueError,match="does not match physical panel"):
        existing_inner_door_feature_finalscene(
            state,panel,existing_render_data=foreign,
        )


def _w800_capability(tmp_path, *, neighbor=None, layers=1,
                     submitted=True, change_state=None, change_proof=None):
    state=_state(neighbor)
    if change_state:
        state.update(change_state)
    index,source,profile=_source(tmp_path)
    inventory=inspect_nfb_dxf_source(source)
    scope=NfbPhysicalScope(
        set_id="setW800",bay_id="bayUpper",version_id="version-1",
        submitted=submitted,inner_door_part_id="inner_door:upper:panel",
    )
    evidence=None
    if submitted:
        # For deliberately mismatched snapshots, generate an otherwise valid
        # witness from the original canonical physical part.
        verified_state=state if change_state is None else _state(neighbor)
        evidence=configured_w800_three_nfb_inner_door_render_data(
            verified_state,"upper",
            rows=(_row(),) if layers==1 else (_row(0),_row(1)),
            index_path=index,source_path=source,profile=profile,
        )
    if change_proof and evidence is not None:
        evidence=change_proof(evidence)
    actual=derive_w800_three_nfb_capability(
        state,"upper",scope=scope,source_inventory=inventory,
        verified_inner_door=evidence,
    )
    return actual


@pytest.mark.parametrize("neighbor,layer_count", [
    (None,1),(400.,1),(None,2),(400.,2),
])
def test_1498_versioned_w800_three_capability_tracks_real_x_y_and_source(
    tmp_path,neighbor,layer_count,
):
    proven=_w800_capability(tmp_path,neighbor=neighbor,layers=layer_count)
    assert proven.schema==CAPABILITY_SCHEMA
    assert proven.revision==CAPABILITY_RULE_REVISION
    assert proven.status==READY
    assert proven.can_manufacture_nfb_inner_door
    assert proven.scope_identity==("setW800","bayUpper","version-1")
    assert proven.physical_part_id=="inner_door:upper:panel"
    assert proven.bay_cell_width_mm==pytest.approx(800.)
    assert proven.blank_cutting_width_mm==pytest.approx(723.)
    assert proven.units_per_layer==3
    assert proven.layer_count==layer_count
    assert proven.x_datum_revision==W800_THREE_DATUM_REVISION
    assert proven.y_datum_revision
    assert proven.model_identity==("士林","400_140X257_107.dxf")
    assert len(proven.source_sha256)==64
    report=proven.report()
    assert report["status"]=="READY"
    assert report["can_manufacture_nfb_inner_door"] is True
    assert report["scope"]["version_id"]=="version-1"
    assert report["model_identity"]==["士林","400_140X257_107.dxf"]


@pytest.mark.parametrize("change", [
    {"w":750.}, {"t":3.}, {"door_gap_w":4.},
    {"multi_door_enabled":False},
])
def test_1498_wrong_w800_manufacturing_part_datum_is_blocked_not_guessed(
    tmp_path, change,
):
    status=_w800_capability(tmp_path,change_state=change)
    assert status.status==BLOCKED
    assert "W800_THREE_ACTUAL_723_CUTTING_X_UNVERIFIED" in status.reasons
    assert not status.can_manufacture_nfb_inner_door


@pytest.mark.parametrize("poison", [
    lambda r:replace(r,verified_hole_locations=()),
    lambda r:replace(r,verified_hole_locations=tuple(
        (p[0],p[1]+9.,p[2],p[3],p[4])
        if i==1 else p for i,p in enumerate(r.verified_hole_locations)
    )),
    lambda r:replace(r,verified_hole_locations=tuple(
        (p[0],p[1],2,p[3],p[4]) for p in r.verified_hole_locations
    )),
    lambda r:replace(r,source_sha256="0"*64),
    lambda r:replace(r,render_data=replace(
        r.render_data,metadata={
            **r.render_data.metadata,"nfb_y_rule_revision":"STALE",
        },
    )),
])
def test_1498_matrix_rejects_stale_x_y_layers_and_source(
    tmp_path,poison,
):
    result=_w800_capability(tmp_path,change_proof=poison)
    assert result.status==BLOCKED
    assert result.reasons
    assert result.report()["can_manufacture_nfb_inner_door"] is False


def test_1498_unconfigured_matrix_is_legacy_not_manufacturing_permission(tmp_path):
    result=_w800_capability(tmp_path,submitted=False)
    assert result.status==LEGACY
    assert not result.can_manufacture_nfb_inner_door
    assert result.report()["status"]=="UNCONFIGURED_LEGACY"
    assert result.model_identity is None
    assert result.source_sha256 is None
