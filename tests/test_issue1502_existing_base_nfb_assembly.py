# -*- coding: utf-8 -*-
"""#1502 physical upper base/ear slots/NFB share original manufacturing owner."""
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_api import (save_part_render_data_dxf, save_resolved_manufacturing_geometry_dxf, save_resolved_manufacturing_geometry_batch_dxf)
from ae_engine.receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)
from ae_engine.receiving_nfb_base_process_projection import (
    build_existing_receiving_base_with_verified_nfb,
)
from ae_engine.sheetmetal_drawing import PolylinePrimitive, CirclePrimitive


def _snapshot():
    snapshot = apply_family_defaults({
        "model": "受電箱", "w":800., "h":1600., "d":350., "t":2.,
        "fw":29., "door_gap_w":3.5, "door_gap_h":3.5,
    })
    snapshot.update({
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.,[1100.,500.]]],
        "inner_doors":[{
            "stable_id":"upper","cell_key":"0:0",
            "included_frame_sides":["top","left","right"],
        }],
    })
    return snapshot


def _upper_base(pattern="LEFT_FLAT_SIDE"):
    central=pattern=="CENTER_DOUBLE_SIDE_FOLD"
    return BasePlatePartSpec(
        width=800.,height=(280. if central else 360. if pattern=="RIGHT_FLAT_SIDE" else 340.),
        thickness=2.,
        shrink_top=20.,shrink_bottom=20.,
        shrink_left=85. if central else 45.,
        shrink_right=85. if central else 45.,
        bend=20.,model_name="受電箱",
        receiving_bend_pattern=pattern,
        physical_id="base_plate",
    )


def _native_original(tmp_path):
    path=tmp_path/"400_140X257_107.dxf"
    doc=ezdxf.new("R2010")
    m=doc.modelspace()
    upper=m.add_lwpolyline(
        [(0.,350.),(57.,350.),(57.,446.),(0.,446.)],
        close=True,dxfattribs={"color":150},
    )
    lower=m.add_lwpolyline(
        [(-50.,0.),(50.,0.),(50.,257.),(-50.,257.)],
        close=True,dxfattribs={"color":3},
    )
    for x in (-40.,-25.,70.,85.):
        m.add_circle((x,398.),2.,dxfattribs={"color":30})
    corners=((35.,410.),(45.,410.),(45.,420.),(35.,420.))
    for i in range(4):
        m.add_line(corners[i],corners[(i+1)%4],dxfattribs={"color":30})
    for x in (10.,16.,22.,28.):
        m.add_line((x,435.),(x+3.,435.),dxfattribs={"color":212})
    for x in (-10.,10.):
        for y in (110.,130.):
            m.add_circle((x,y),1.4,dxfattribs={"color":3})
    doc.saveas(path)
    digest=sha256(path.read_bytes()).hexdigest()
    profile=NfbUpperSourceProfile(
        brand="士林",indexed_filename=path.name,
        source_sha256=digest,upper_handle=upper.dxf.handle,
        upper_size_mm=(57.,96.),
        source_alias_status="SOURCE_ALIAS_SHA256_IDENTICAL",
        revision="SYNTHETIC_TWO_GROUP_1502",
    )
    return path,profile,lower.dxf.handle


def _verified(profile):
    locations=(
        ("nfb:upper:1", -100., 1, 0, 0),
        ("nfb:upper:2", 100., 1, 0, 90),
    )
    return NfbValidatedInnerDoorRender(
        render_data=SimpleNamespace(metadata={
            "nfb_trial_status":VALIDATED,
            "nfb_trial_export_approved":True,
        }),
        part_id="inner_door:upper:panel",
        indexed_model_key=(profile.brand,profile.indexed_filename),
        source_sha256=profile.source_sha256,
        physical_hole_ids=tuple(row[0] for row in locations),
        verified_hole_locations=locations,
    )


def _build(tmp_path, *, base=None, snapshot=None, proof=None):
    path,profile,lower=_native_original(tmp_path)
    return build_existing_receiving_base_with_verified_nfb(
        snapshot=snapshot or _snapshot(),
        inner_door_id="upper",
        base_spec=base or _upper_base(),
        verified_inner_door=proof or _verified(profile),
        source_path=path,
        profile=profile,
        lower_reference_handle=lower,
    )


@pytest.mark.parametrize("pattern",("LEFT_FLAT_SIDE","CENTER_DOUBLE_SIDE_FOLD","RIGHT_FLAT_SIDE"))
def test_existing_upper_base_ear_NFB_finalscene_are_one_real_part(tmp_path,pattern):
    combined=_build(tmp_path,base=_upper_base(pattern))
    assert not combined.manufacturing_ready
    real=combined.render_data
    assert real.metadata["stable_id"]=="base_plate"
    assert real.metadata["nfb_base_mfg2_release_approved"] is False
    assert real.metadata["nfb_physical_hole_ids"]==(
        "nfb:upper:1","nfb:upper:2",
    )
    cuts=[x for x in real.scene.primitives if
          isinstance(x,PolylinePrimitive) and x.layer=="CUTTING" and x.closed]
    # Exterior + 4 EAR slots + 2 upper native source closed contours.
    assert len(cuts)==7
    native=[x for x in real.scene.primitives if
            isinstance(x,CirclePrimitive)
            and x.source_type=="NFB_LOWER_NATIVE_FIXING_CIRCLE"]
    assert len(native)==8  # 4 original lower screw circles per verified NFB
    assert len({x.source_id for x in native})==8
    assert real.material.area>0
    assert real.unfolded_topology.piece_id=="base_plate"
    assert real.metadata["nfb_source_sha256"]==combined.projection.source_sha256
    assert real.metadata["receiving_base_ear_mount_center_world_xy_mm"]==pytest.approx((0.,250.))
    assert real.metadata["receiving_base_nfb_row_center_world_xy_mm"]==pytest.approx((0.,250.))
    assert real.metadata["receiving_base_ear_weld_z_verified"] is False
    # Headless original serialization must use the SAME FinalScene, not a
    # freshly generated legacy base without the configured NFB features.
    out=tmp_path/(pattern+".dxf")
    save_part_render_data_dxf(real,out)
    imported=ezdxf.readfile(out).modelspace()
    source_circles=sorted(
        (round(p.center.x,6),round(p.center.y,6),round(p.radius,6))
        for p in real.scene.primitives
        if isinstance(p,CirclePrimitive) and p.layer=="CUTTING"
    )
    saved_circles=sorted(
        (round(e.dxf.center.x,6),round(e.dxf.center.y,6),round(e.dxf.radius,6))
        for e in imported
        if e.dxftype()=="CIRCLE" and e.dxf.layer=="CUTTING"
    )
    assert saved_circles==source_circles  # exact NFB screw/CUTTING count & XY
    saved_cuts=[e for e in imported
                if e.dxftype()=="LWPOLYLINE" and e.dxf.layer=="CUTTING" and e.closed]
    saved_marks=[e for e in imported
                 if e.dxftype()=="LWPOLYLINE" and e.dxf.layer=="MARKING"]
    assert len(saved_cuts)==len(cuts)
    source_marks=[p for p in real.scene.primitives
                  if isinstance(p,PolylinePrimitive) and p.layer=="MARKING"]
    assert len(saved_marks)==len(source_marks)
    assert len(saved_cuts)==7 and len(saved_marks)==8


def test_lower_bay_does_not_create_second_base_plate(tmp_path):
    with pytest.raises(ValueError,match="actual physical identity"):
        _build(tmp_path,base=replace(_upper_base(),physical_id="base_plate_c1_r2"))
    with pytest.raises(ValueError,match="actual physical identity"):
        _build(tmp_path,base=replace(_upper_base(),physical_id="base_plate_c1_r1"))


def test_source_owner_and_geometry_fail_closed(tmp_path):
    with pytest.raises(ValueError,match="bend-pattern"):
        _build(tmp_path,base=replace(_upper_base(),receiving_bend_pattern=None))
    with pytest.raises(ValueError,match="cannot exceed upper"):
        _build(tmp_path,base=replace(_upper_base(),height=1600.))
    with pytest.raises(ValueError,match="box W/T"):
        _build(tmp_path,base=replace(_upper_base(),width=900.))
    with pytest.raises(ValueError,match="Receiving cabinet"):
        _build(tmp_path,base=replace(_upper_base(),model_name="金庫型"))



def test_two_real_NFB_heights_cannot_share_one_assumed_ear_group(tmp_path):
    path,profile,lower=_native_original(tmp_path)
    two=NfbValidatedInnerDoorRender(
        render_data=SimpleNamespace(metadata={
            "nfb_trial_status":VALIDATED,
            "nfb_trial_export_approved":True,
        }),
        part_id="inner_door:upper:panel",
        indexed_model_key=(profile.brand,profile.indexed_filename),
        source_sha256=profile.source_sha256,
        physical_hole_ids=("nfb:upper:1","nfb:upper:2"),
        verified_hole_locations=(
            ("nfb:upper:1",-100.,2,0,0),
            ("nfb:upper:2",100.,2,1,0),
        ),
    )
    with pytest.raises(ValueError,match="distinct actual ear/base groups"):
        build_existing_receiving_base_with_verified_nfb(
            snapshot=_snapshot(),inner_door_id="upper",
            base_spec=_upper_base(),verified_inner_door=two,
            source_path=path,profile=profile,
            lower_reference_handle=lower,
        )


@pytest.mark.parametrize("pattern", (
    "LEFT_FLAT_SIDE", "CENTER_DOUBLE_SIDE_FOLD", "RIGHT_FLAT_SIDE",
))
def test_proven_base_cutting_partial_dxf_is_independent_of_ear_weld_z(tmp_path, pattern):
    built = _build(tmp_path, base=_upper_base(pattern))
    assert built.manufacturing_ready is False
    assert built.render_data.metadata["receiving_base_ear_weld_z_verified"] is False
    resolved = SimpleNamespace(parts=(SimpleNamespace(
        part_key="base_plate", render_data=built.render_data,
    ),))
    # A complete-cabinet release remains blocked.
    blocked_root = tmp_path / "whole-assembly"
    with pytest.raises(ValueError, match="NFB_BASE_MFG2_NOT_RELEASED_FOR_BATCH_EXPORT"):
        save_resolved_manufacturing_geometry_dxf(resolved, blocked_root)
    assert not blocked_root.exists()
    # One verified physical plate may export its own CUTTING DXF.
    root = tmp_path / "part-only"
    exported = save_resolved_manufacturing_geometry_dxf(
        resolved, root, part_only=True,
    )
    assert set(exported) == {"base_plate"}
    dxf = ezdxf.readfile(exported["base_plate"]).modelspace()
    screws = [e for e in dxf if e.dxftype() == "CIRCLE"
              and e.dxf.layer == "CUTTING"]
    assert len(screws) >= 8
    assert built.render_data.metadata["nfb_base_mfg2_release_approved"] is False


def test_part_only_batch_rejects_unproved_nfb_before_any_output(tmp_path):
    built = _build(tmp_path)
    from dataclasses import replace as dataclass_replace
    data = dataclass_replace(built.render_data, metadata={
        **dict(built.render_data.metadata),
        "nfb_source_sha256": "0" * 64,
        "nfb_physical_hole_ids": ("different-owner",),
    })
    batch = (("setA__bay1", SimpleNamespace(parts=(
        SimpleNamespace(part_key="base_plate", render_data=data),))),)
    root = tmp_path / "wrong-owner"
    with pytest.raises(ValueError, match="NFB_BASE_PART_SOURCE_(CUTTING_INCOMPLETE|HOLE_MAPPING_UNVERIFIED)"):
        save_resolved_manufacturing_geometry_batch_dxf(
            batch, root, part_only=True,
        )
    assert not root.exists()


def _repeated_native_quartet(tmp_path):
    """Original-style two views, with a large nonintegral schematic offset."""
    path, profile, lower = _native_original(tmp_path)
    doc = ezdxf.readfile(path)
    circles = tuple(e for e in doc.modelspace()
                    if e.dxftype() == "CIRCLE" and e.dxf.color == 30)
    for upper, (x, y) in zip(circles, ((-10., -10.), (-10., 10.),
                                     (10., -10.), (10., 10.))):
        upper.dxf.center = (28.5 + x, 398. + y)
        upper.dxf.radius = 1.4
    # Matching native lower quartet remains at centroid (0, 120).
    from ezdxf.math import Matrix44
    shift = Matrix44.translate(3743.467233573938, 2162.8091805827455, 0)
    for entity in doc.modelspace():
        entity.transform(shift)
    doc.saveas(path)
    return path, replace(profile, source_sha256=sha256(path.read_bytes()).hexdigest()), lower


def _build_repeated_native(tmp_path, pattern="LEFT_FLAT_SIDE", angle=0):
    path, profile, lower = _repeated_native_quartet(tmp_path)
    proof = _verified(profile)
    proof = replace(proof, verified_hole_locations=tuple(
        (*row[:4], angle) for row in proof.verified_hole_locations))
    return build_existing_receiving_base_with_verified_nfb(
        snapshot=_snapshot(), inner_door_id="upper", base_spec=_upper_base(pattern),
        verified_inner_door=proof, source_path=path, profile=profile,
        lower_reference_handle=lower,
    )


@pytest.mark.parametrize("pattern", ("LEFT_FLAT_SIDE", "RIGHT_FLAT_SIDE",
                                     "CENTER_DOUBLE_SIDE_FOLD"))
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
def test_repeated_native_fixing_quartet_has_four_cuts_per_owner(tmp_path, pattern, angle):
    combined = _build_repeated_native(tmp_path, pattern, angle)
    circles = tuple(p for p in combined.render_data.scene.primitives
                    if isinstance(p, CirclePrimitive) and p.layer == "CUTTING")
    assert len(circles) == 8
    assert all(p.source_type == "NFB_LOWER_NATIVE_FIXING_CIRCLE" for p in circles)
    aliases = combined.projection.native_fixing_aliases
    assert len(aliases) == 8
    assert all(a.source_sha256 == combined.projection.source_sha256 for a in aliases)
    assert len({(a.owner_hole_id, a.upper_handle) for a in aliases}) == 8
    assert len({(a.owner_hole_id, a.lower_handle) for a in aliases}) == 8
    resolved = SimpleNamespace(parts=(SimpleNamespace(
        part_key="base_plate", render_data=combined.render_data),))
    result = save_resolved_manufacturing_geometry_dxf(
        resolved, tmp_path / "part-only-alias", part_only=True)
    saved = tuple(e for e in ezdxf.readfile(result["base_plate"]).modelspace()
                  if e.dxftype() == "CIRCLE" and e.dxf.layer == "CUTTING")
    assert len(saved) == 8
    assert sorted((round(e.dxf.center.x, 6), round(e.dxf.center.y, 6),
                   round(e.dxf.radius, 6)) for e in saved) == sorted(
        (round(p.center.x, 6), round(p.center.y, 6), round(p.radius, 6)) for p in circles)
    assert not combined.manufacturing_ready
    assert combined.render_data.metadata["receiving_base_ear_weld_z_verified"] is False


def test_partial_native_quartet_match_is_not_silently_deduplicated(tmp_path):
    path, profile, lower = _repeated_native_quartet(tmp_path)
    doc = ezdxf.readfile(path)
    upper = next(e for e in doc.modelspace()
                 if e.dxftype() == "CIRCLE" and e.dxf.color == 30)
    upper.dxf.radius = 1.5
    doc.saveas(path)
    profile = replace(profile, source_sha256=sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="quartet alias incomplete"):
        build_existing_receiving_base_with_verified_nfb(
            snapshot=_snapshot(), inner_door_id="upper", base_spec=_upper_base(),
            verified_inner_door=_verified(profile), source_path=path, profile=profile,
            lower_reference_handle=lower)


@pytest.mark.parametrize("mutation", ("sha", "owner", "position", "missing", "duplicate"))
def test_part_only_rejects_changed_native_alias_evidence_before_write(tmp_path, mutation):
    combined = _build_repeated_native(tmp_path)
    aliases = combined.projection.native_fixing_aliases
    if mutation == "sha":
        aliases = (replace(aliases[0], source_sha256="0" * 64), *aliases[1:])
    elif mutation == "owner":
        aliases = (replace(aliases[0], owner_hole_id="other-owner"), *aliases[1:])
    elif mutation == "position":
        aliases = (replace(aliases[0], center_uv_mm=(0., 0.)), *aliases[1:])
    elif mutation == "missing":
        aliases = aliases[1:]
    else:
        aliases = (*aliases, aliases[0])
    data = replace(combined.render_data, metadata={
        **dict(combined.render_data.metadata), "nfb_native_fixing_aliases": aliases})
    resolved = SimpleNamespace(parts=(SimpleNamespace(part_key="base_plate", render_data=data),))
    root = tmp_path / "unverified-alias"
    with pytest.raises(ValueError, match="NFB_BASE_PART_(NATIVE_ALIAS|SOURCE_HOLE_MAPPING)_UNVERIFIED"):
        save_resolved_manufacturing_geometry_dxf(resolved, root, part_only=True)
    assert not root.exists()


def test_nfb_x_edit_moves_only_its_real_screw_circles_not_base_or_welded_ear_x(tmp_path):
    """The user-authorized manufacturing regression: plate center X never moves."""
    path, profile, lower = _native_original(tmp_path)
    original = _verified(profile)
    # Both NFBs move +10mm right; a previous bug moved the WHOLE Base
    # Plate 10mm as well and thus cancelled their real screw-hole offset.
    edited = replace(
        original,
        verified_hole_locations=tuple(
            (hole_id, x + 10., layer_count, slot, angle)
            for hole_id, x, layer_count, slot, angle
            in original.verified_hole_locations
        ),
    )
    inputs=dict(
        snapshot=_snapshot(),
        inner_door_id="upper",
        base_spec=_upper_base(),
        source_path=path,
        profile=profile,
        lower_reference_handle=lower,
    )
    before=build_existing_receiving_base_with_verified_nfb(
        verified_inner_door=original, **inputs
    )
    after=build_existing_receiving_base_with_verified_nfb(
        verified_inner_door=edited, **inputs
    )
    for result in (before, after):
        assert result.render_data.metadata[
            "receiving_base_ear_mount_center_world_xy_mm"
        ] == pytest.approx((0.,250.))
        assert result.render_data.metadata[
            "receiving_base_nfb_row_center_world_xy_mm"
        ] == pytest.approx((0.,250.))
        assert result.render_data.unfolded_topology.piece_id == "base_plate"
        assert result.render_data.material.area > 0

    def screws(result):
        return {
            p.source_id:(p.center.x,p.center.y)
            for p in result.render_data.scene.primitives
            if isinstance(p,CirclePrimitive)
            and p.source_type=="NFB_LOWER_NATIVE_FIXING_CIRCLE"
        }

    a,b=screws(before),screws(after)
    assert a.keys()==b.keys()
    assert len(a)==8
    for key in a:
        assert b[key][0]-a[key][0] == pytest.approx(10.)
        assert b[key][1]-a[key][1] == pytest.approx(0.)
    # Ear mounting holes in the actual source plate are still owned by its
    # unchanged source topology; the NFB screw quartet alone shifts.
