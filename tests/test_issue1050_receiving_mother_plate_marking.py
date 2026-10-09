from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.cabinet_types import receiving
from ae_engine.contracts import (
    BoxBodyPartSpec,
    EndCapPartSpec,
    FoldProfileSegment,
    ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
)
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.inner_door_frames import derive_all_inner_door_frames
from ae_engine.manufacturing_api import (
    build_box_body_divider_render_data,
    build_box_body_structure_render_data,
    build_inner_door_frame_render_data,
    build_part_render_data,
    save_resolved_manufacturing_geometry_dxf,
)
from ae_engine.receiving_joint_marking import resolve_receiving_joint_markings
from ae_engine.sheetmetal_drawing import LinePrimitive
from phase6_fold_profiles import (
    build_box_body_profile,
    build_linked_endcap_xy_profiles,
    profile_to_fold_segments,
)
from phase6_manufacturing_geometry import _phase6_assembly_placement_for_part


DIVIDER_ID = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
FRAME_IDS = (
    "inner_door:upper:top_frame",
    "inner_door:upper:left_frame",
    "inner_door:upper:right_frame",
)


def _snapshot():
    return {
        "model": "受電箱",
        "w": 800.0,
        "h": 1600.0,
        "d": 350.0,
        "t": 2.0,
        "fw": 29.0,
        "zl1": 24.0,
        "zl2": 24.0,
        "zr1": 17.0,
        "zr2": 18.0,
        "yl1": 15.0,
        "yr1": 15.0,
        "ytop1": 16.0,
        "ybottom1": 15.0,
        "door_gap_w": 3.5,
        "door_gap_h": 3.5,
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{
            "stable_id": "upper",
            "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    }


def _part(snapshot, key, render_data, x_profile=(), y_profile=()):
    placement, offset = _phase6_assembly_placement_for_part(snapshot, key)
    return ResolvedManufacturingPart(
        part_key=key,
        render_data=render_data,
        x_profile=tuple(x_profile),
        y_profile=tuple(y_profile),
        placement=placement,
        offset=tuple(offset),
    )


def _full_receiving_geometry(snapshot):
    box_profile = build_box_body_profile(snapshot)
    structure_state = receiving.resolve_box_body_structure_state(None)
    box_body = build_box_body_structure_render_data(BoxBodyPartSpec(
        width=800.0,
        height=1600.0,
        depth=350.0,
        thickness=2.0,
        frame_width=29.0,
        model_name="受電箱",
        zl1=24.0,
        zl2=24.0,
        zr1=17.0,
        zr2=18.0,
        z_comp=0.0,
        fold_profile=profile_to_fold_segments(box_profile),
        structure_state=structure_state,
    ))

    head_profiles = build_linked_endcap_xy_profiles(snapshot, box_profile)["head"]
    head = build_part_render_data(EndCapPartSpec(
        width=800.0,
        height=1600.0,
        depth=350.0,
        thickness=2.0,
        frame_width=29.0,
        model_name="受電箱",
        is_tail=False,
        fold_left=15.0,
        fold_right=15.0,
        fold_top=16.0,
        fold_bottom=15.0,
        box_fold_left=24.0,
        box_fold_right=18.0,
        fold_profile_x=profile_to_fold_segments(head_profiles["X"]),
        fold_profile_y=profile_to_fold_segments(head_profiles["Y"]),
        corner_policy=receiving.endcap_corner_policy(
            frame_width=29.0,
            thickness=2.0,
            side_rear_bend=18.0,
        ),
        depth_comp_t=2.0,
        box_body_structure_state=structure_state,
    ))

    parts = [
        _part(snapshot, "box_body", box_body),
        _part(
            snapshot,
            "head",
            head,
            profile_to_fold_segments(head_profiles["X"]),
            profile_to_fold_segments(head_profiles["Y"]),
        ),
    ]

    for divider in derive_box_body_dividers(
        snapshot["door_layout_columns"],
        depth=float(snapshot["d"]),
        thickness=float(snapshot["t"]),
        layout_scope=snapshot["door_layout_scope"],
        model_name=snapshot["model"],
        frame_width=float(snapshot["fw"]),
    ):
        parts.append(_part(
            snapshot,
            divider.stable_id,
            build_box_body_divider_render_data(divider),
            divider.fold_profile,
            (FoldProfileSegment(
                length=float(divider.span),
                angle=None,
                phase6_key="divider_span",
            ),),
        ))

    frames = derive_all_inner_door_frames(
        cabinet_family_policy.derive_inner_door_frame_sets(snapshot)
    )
    for frame in frames:
        parts.append(_part(
            snapshot,
            frame.stable_id,
            build_inner_door_frame_render_data(frame),
            frame.fold_profile,
            (FoldProfileSegment(
                length=float(frame.span),
                angle=None,
                phase6_key="frame_span",
            ),),
        ))
    return ResolvedManufacturingGeometry(parts=tuple(parts))


def _rows(render_data):
    return tuple(dict(render_data.metadata or {}).get("joint_markings") or ())


def _mark_lines(render_data):
    return tuple(
        primitive
        for primitive in tuple(render_data.scene.primitives or ())
        if isinstance(primitive, LinePrimitive)
        and str(primitive.layer).upper() == "MARKING"
    )


def _piece(geometry, role):
    body = geometry.part("box_body").render_data
    return next(piece.render_data for piece in body.pieces if piece.role == role)


def _resolved():
    snapshot = _snapshot()
    result = resolve_receiving_joint_markings(
        snapshot,
        _full_receiving_geometry(snapshot),
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )
    return snapshot, result


def test_receiving_marks_all_four_receiver_mother_plates_from_canonical_world_geometry():
    _snapshot_data, result = _resolved()

    emitted = tuple(row for row in result.results if row.status == "EMITTED")
    if len(emitted) != 5:
        # Actionable diagnostics for physical mating geometry regressions.
        # Show actual folded skin plane positions instead of guessing a shift.
        from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry
        from ae_engine.receiving_joint_marking import (
            _last_frame_flange_skins, _mapped_plane_groups,
        )
        snap = _snapshot()
        world = _phase6_build_joint_world_geometry(
            _full_receiving_geometry(snap).parts, (800.0, 1600.0, 350.0), 2.0
        )
        frames = {
            row.stable_id: row
            for row in derive_all_inner_door_frames(
                cabinet_family_policy.derive_inner_door_frame_sets(snap)
            )
        }
        descriptions = []
        for locator, frame_id, axis in (
            ("box_body:left_side", FRAME_IDS[1], 0),
            ("box_body:right_side", FRAME_IDS[2], 0),
            ("head", FRAME_IDS[0], 1),
        ):
            loc = world["mapped_skin_triangles_by_part"].get(locator, ())
            frm = _last_frame_flange_skins(
                frames[frame_id], world["mapped_skin_triangles_by_part"].get(frame_id, ())
            )
            mother_planes = sorted({
                round(float(g[0].world[0][axis]), 4)
                for g in _mapped_plane_groups(loc)
            })
            flange_planes = sorted({
                round(float(g[0].world[0][axis]), 4)
                for g in _mapped_plane_groups(frm)
            })
            descriptions.append((locator, frame_id, mother_planes, flange_planes))
        pytest.fail(
            "Expected five actual physical contact MARKING rows; "
            f"results={[(x.locator_part_id,x.attached_part_id,x.status,x.diagnostic_code,x.diagnostic_detail) for x in result.results]}; "
            f"skin_planes={descriptions}"
        )
    assert len(emitted) == 5
    assert {(row.locator_part_id, row.attached_part_id) for row in emitted} == {
        (DIVIDER_ID, "inner_door:upper:left_frame"),
        (DIVIDER_ID, "inner_door:upper:right_frame"),
        ("box_body:left_side", "inner_door:upper:left_frame"),
        ("box_body:right_side", "inner_door:upper:right_frame"),
        ("head", "inner_door:upper:top_frame"),
    }

    divider_results = tuple(row for row in emitted if row.locator_part_id == DIVIDER_ID)
    assert all(
        float(row.evidence["contact_evidence"]["plane_separation"]) == 0.0
        for row in divider_results
    )

    # Side/head MARKING is legal only when the FINAL 22-mm frame flange
    # actually touches its mother plate. In particular, a projected but
    # physically separated frame must never produce manufacturing marks.
    physical = tuple(row for row in emitted if row.locator_part_id != DIVIDER_ID)
    assert len(physical) == 3
    assert all(
        row.evidence["contact_evidence"]["contact_mode"]
        == "VERIFIED_LAST_22_MM_PHYSICAL_SKIN"
        for row in physical
    )
    assert all(
        abs(float(row.evidence["contact_evidence"]["projection_distance"])) <= 1e-6
        for row in physical
    )

    assert len(_rows(_piece(result.geometry, "left_side"))) == 1
    assert len(_rows(_piece(result.geometry, "right_side"))) == 1
    assert len(_rows(result.geometry.part("head").render_data)) == 1
    assert len(_rows(result.geometry.part(DIVIDER_ID).render_data)) == 2

    for frame_id in FRAME_IDS:
        assert _rows(result.geometry.part(frame_id).render_data) == ()
        assert _mark_lines(result.geometry.part(frame_id).render_data) == ()


def test_receiver_marking_metadata_binds_same_flat_and_world_contact_geometry():
    _snapshot_data, result = _resolved()
    owners = (
        _piece(result.geometry, "left_side"),
        _piece(result.geometry, "right_side"),
        result.geometry.part("head").render_data,
        result.geometry.part(DIVIDER_ID).render_data,
    )
    rows = tuple(row for owner in owners for row in _rows(owner))
    assert len(rows) == 5
    for row in rows:
        assert row["source"] == "JOINT_PLACEMENT_MARKING"
        assert row["geometry_source"] == "RECEIVER_MATING_CONTACT_BACKPROJECTION"
        assert len(row["world_p1"]) == len(row["world_p2"]) == 3
        assert row["p1"] != row["p2"]
        assert row["world_p1"] != row["world_p2"]


def test_dxf_exports_receiver_marks_from_the_same_final_scene_primitives(tmp_path: Path):
    _snapshot_data, result = _resolved()
    outputs = save_resolved_manufacturing_geometry_dxf(
        result.geometry, tmp_path, overwrite=True
    )
    expected_counts = {
        "box_body:box_body_left_side": 1,
        "box_body:box_body_right_side": 1,
        "head": 1,
        DIVIDER_ID: 2,
    }
    for part_key, count in expected_counts.items():
        doc = ezdxf.readfile(outputs[part_key])
        marking = [
            entity
            for entity in doc.modelspace()
            if entity.dxftype() == "LINE"
            and str(entity.dxf.layer).upper() == "MARKING"
        ]
        assert len(marking) == count
