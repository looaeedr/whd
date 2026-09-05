from __future__ import annotations

import pytest


def test_one_inner_door_derives_four_stable_frame_parts():
    from ae_engine.inner_door_frames import derive_inner_door_frames

    frames = derive_inner_door_frames(
        "upper-A",
        spans={"top": 600, "bottom": 600, "left": 900, "right": 900},
        thickness=2,
    )
    assert tuple(frame.side for frame in frames) == ("top", "bottom", "left", "right")
    assert tuple(frame.stable_id for frame in frames) == (
        "inner_door:upper-A:top_frame",
        "inner_door:upper-A:bottom_frame",
        "inner_door:upper-A:left_frame",
        "inner_door:upper-A:right_frame",
    )
    assert frames[0].signed_fold_chain == (22.0, 46.0, 22.0)
    assert frames[1].signed_fold_chain == (22.0, 46.0, 22.0)
    assert frames[3].signed_fold_chain == (22.0, 46.0, 22.0)
    assert frames[2].signed_fold_chain == (-22.0, 20.0, 46.0, 22.0)
    assert frames[2].material_lengths == (22.0, 20.0, 46.0, 22.0)
    assert all(length > 0 for frame in frames for length in frame.material_lengths)


def test_multiple_inner_doors_do_not_collide_and_rerender_keeps_ids():
    from ae_engine.inner_door_frames import derive_inner_door_frames

    one = derive_inner_door_frames(
        "door-A", spans={"top": 500, "bottom": 500, "left": 800, "right": 800}, thickness=2
    )
    two = derive_inner_door_frames(
        "door-B", spans={"top": 500, "bottom": 500, "left": 800, "right": 800}, thickness=2
    )
    repeat = derive_inner_door_frames(
        "door-A", spans={"top": 525, "bottom": 525, "left": 775, "right": 775}, thickness=2
    )
    assert set(f.stable_id for f in one).isdisjoint(f.stable_id for f in two)
    assert tuple(f.stable_id for f in one) == tuple(f.stable_id for f in repeat)


def test_zero_inner_doors_generate_zero_frames():
    from ae_engine.inner_door_frames import derive_all_inner_door_frames

    assert derive_all_inner_door_frames(()) == ()


def test_frame_render_data_has_own_blank_bends_and_fold_profile():
    from ae_engine.inner_door_frames import derive_inner_door_frames
    from ae_engine.manufacturing_api import build_inner_door_frame_render_data, measure_unfolded_blanks

    frame = derive_inner_door_frames(
        "door-A", spans={"top": 500, "bottom": 500, "left": 800, "right": 800}, thickness=2
    )[2]
    data = build_inner_door_frame_render_data(frame)
    blank = measure_unfolded_blanks(data, part_key=frame.stable_id)[0]
    assert blank.width == pytest.approx(sum(frame.material_lengths))
    assert blank.height == pytest.approx(800.0)
    assert len(data.fold_guides) == len(frame.material_lengths) - 1
    assert data.metadata["stable_id"] == frame.stable_id
    assert data.metadata["signed_fold_chain"] == frame.signed_fold_chain
    assert tuple(seg.length for seg in frame.fold_profile) == frame.material_lengths
    assert tuple(seg.angle for seg in frame.fold_profile[:-1]) == (-90.0, 90.0, 90.0)

    from ae_engine.assembly_geometry import folded_mesh_with_flat_uv_from_polygon
    from ae_engine.contracts import FoldProfileSegment
    triangles = folded_mesh_with_flat_uv_from_polygon(
        data.material, frame.fold_profile, (FoldProfileSegment(frame.span),),
        fold_guides=data.fold_guides,
    )
    z_values = [point[2] for triangle in triangles for point in triangle.local]
    assert triangles
    assert max(z_values) - min(z_values) > 1.0


def test_workspace_sync_adds_selectable_frames_and_removes_orphans():
    from ae_engine.inner_door_frames import InnerDoorFrameSet
    from phase6_designer_workspace import Phase6DesignerWorkspace

    workspace = Phase6DesignerWorkspace.from_snapshot({"existing_parts": ["box_body", "door"]})
    request = InnerDoorFrameSet(
        inner_door_id="upper-A",
        spans={"top": 500, "bottom": 500, "left": 800, "right": 800},
        thickness=2,
    )
    from ae_engine.inner_door_frames import derive_all_inner_door_frames

    first = derive_all_inner_door_frames((request,))
    workspace.sync_derived_parts(
        namespace="inner_door:",
        part_profiles={
            frame.stable_id: {
                "X": [
                    {"len": row.length, **({"angle": row.angle} if row.angle is not None else {}), "phase6_key": row.phase6_key}
                    for row in frame.fold_profile
                ],
                "Y": [{"len": frame.span, "phase6_key": "inner_door_frame_span"}],
            }
            for frame in first
        },
    )
    assert len(first) == 4
    assert all(key in workspace.available_parts for key in (f.stable_id for f in first))
    assert workspace.select_part(first[0].stable_id)
    assert workspace.selected_part == first[0].stable_id

    second = derive_all_inner_door_frames(())
    workspace.sync_derived_parts(namespace="inner_door:", part_profiles={})
    assert second == ()
    assert all(not key.startswith("inner_door:upper-A:") for key in workspace.available_parts)
    assert workspace.selected_part is None
