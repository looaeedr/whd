from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_piece_dimensions_finalscene_and_blank_are_one_contract():
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data, measure_unfolded_blanks
    from phase6_box_body_structure import BoxBodyStructureType, default_box_body_structure_state, set_active_structure
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments

    snapshot = {
        "w": 1200.0, "h": 1600.0, "d": 400.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
    }
    state = set_active_structure(default_box_body_structure_state(), BoxBodyStructureType.TWO_PIECE_W_SPLIT)
    spec = BoxBodyPartSpec(
        width=snapshot["w"], height=snapshot["h"], depth=snapshot["d"],
        thickness=snapshot["t"], frame_width=snapshot["fw"],
        fold_profile=profile_to_fold_segments(build_box_body_profile(snapshot)),
        structure_state=state,
    )
    data = build_box_body_structure_render_data(spec)
    blanks = measure_unfolded_blanks(data, part_key="box_body")
    assert len(data.pieces) == len(blanks) == 2
    for piece, blank in zip(data.pieces, blanks):
        assert piece.material_dimensions == pytest.approx((blank.width, blank.height))
        assert piece.material_dimensions == pytest.approx(
            (piece.render_data.unfolded_topology.width, piece.render_data.unfolded_topology.height)
        )
        assert piece.formed_outer_dimensions == pytest.approx((600.0, 1596.0))


def test_frame_and_divider_stable_parts_share_workspace_finalscene_and_dxf(tmp_path):
    from ae_engine.door_dividers import (
        derive_box_body_dividers, divider_part_profiles, resolve_inner_door_lower_frame_role,
    )
    from ae_engine.cabinet_types import receiving
    from ae_engine.inner_door_frames import derive_all_inner_door_frames
    from ae_engine.manufacturing_api import (
        build_box_body_divider_render_data, build_inner_door_frame_render_data,
        measure_unfolded_blanks, save_part_render_data_dxf,
    )
    from phase6_designer_workspace import Phase6DesignerWorkspace

    dividers = derive_box_body_dividers(
        [(800.0, [1100.0, 500.0])], depth=350.0, thickness=2.0,
        layout_scope="receiving-main",
    )
    assert len(dividers) == 1
    divider = dividers[0]
    role = resolve_inner_door_lower_frame_role("upper", dividers)
    assert role is not None and role.divider_stable_id == divider.stable_id

    # Receiving derives the three real frame spans from the upper outer-door
    # finished face: left/right/top each move inward by the confirmed 50 mm;
    # the bottom physical frame is the shared box-body divider.
    receiving_snapshot = receiving.apply_family_defaults({"t": 2.0})
    frames = derive_all_inner_door_frames(receiving.derive_inner_door_frame_sets(receiving_snapshot))
    assert next(frame.span for frame in frames if frame.side == "top") == pytest.approx(627.0)
    assert {frame.side for frame in frames} == {"top", "left", "right"}
    assert all(frame.side != "bottom" for frame in frames)

    workspace = Phase6DesignerWorkspace.from_snapshot({"existing_parts": ["box_body", "door"]})
    workspace.sync_derived_parts(namespace="box_body:divider:", part_profiles=divider_part_profiles(dividers))
    frame_profiles = {
        frame.stable_id: {
            "X": [
                {"len": row.length, **({"angle": row.angle} if row.angle is not None else {}), "phase6_key": row.phase6_key}
                for row in frame.fold_profile
            ],
            "Y": [{"len": frame.span, "phase6_key": "inner_door_frame_span"}],
        }
        for frame in frames
    }
    workspace.sync_derived_parts(namespace="inner_door:", part_profiles=frame_profiles)

    for part in (divider, *frames):
        assert part.stable_id in workspace.available_parts
        assert workspace.select_part(part.stable_id)
        if part is divider:
            render = build_box_body_divider_render_data(part)
        else:
            render = build_inner_door_frame_render_data(part)
        blank = measure_unfolded_blanks(render, part_key=part.stable_id)[0]
        assert blank.width == pytest.approx(sum(part.material_lengths))
        assert blank.height == pytest.approx(part.span)
        output = tmp_path / f"{part.stable_id.replace(':', '_')}.dxf"
        save_part_render_data_dxf(render, output)
        doc = ezdxf.readfile(output)
        assert len(list(doc.modelspace())) > 0


def _receiving_endcap_spec(*, tail: bool):
    from ae_engine.contracts import EndCapPartSpec
    from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection, FourCornerTypePolicy

    bottom = CornerTypeSelection(CornerTypeId.CROSS)
    top = CornerTypeSelection(CornerTypeId.INSERT_OVERLAY)
    policy = FourCornerTypePolicy(bottom, bottom, top, top, fw=29.0, bottom_fw=17.0)
    return EndCapPartSpec(
        width=800, height=1600, depth=350, thickness=2, frame_width=29,
        model_name="受電箱", is_tail=tail,
        fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
        corner_policy=policy, depth_comp_t=2.0,
    )


def test_baseline_holes_nameplate_and_endcaps_are_same_finalscene_used_by_dxf(tmp_path):
    from ae_engine.contracts import DoorPartSpec
    from ae_engine.manufacturing_api import ManufacturingContext, build_part_render_data, save_part_render_data_dxf
    from ae_engine.sheetmetal_drawing import CirclePrimitive

    ctx = ManufacturingContext(resource_root=_root())
    door = DoorPartSpec(
        width=800, height=1600, thickness=2, frame_width=29,
        model_name="受電箱", gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=19, fold_top=19, fold_bottom=19,
        nameplate_center_datum_top=140,
    )
    cases = [("door", door, "nameplate_mount", 2)] + [
        ("head", _receiving_endcap_spec(tail=False), "baseline_endcap_hole", 3),
        ("tail", _receiving_endcap_spec(tail=True), "baseline_endcap_hole", 3),
    ]
    for key, spec, source_type, smoke_count in cases:
        render = build_part_render_data(spec, ctx)
        circles = tuple(
            p for p in render.scene.primitives
            if isinstance(p, CirclePrimitive) and getattr(p, "source_type", None) == source_type
        )
        assert len(circles) == smoke_count
        assert len({p.source_id for p in circles}) == smoke_count
        path = tmp_path / f"{key}.dxf"
        save_part_render_data_dxf(render, path)
        doc = ezdxf.readfile(path)
        exported_centers = {
            (round(float(e.dxf.center.x), 6), round(float(e.dxf.center.y), 6), round(float(e.dxf.radius), 6))
            for e in doc.modelspace() if e.dxftype() == "CIRCLE"
        }
        for circle in circles:
            expected = (round(circle.center.x, 6), round(circle.center.y, 6), round(circle.radius, 6))
            assert expected in exported_centers


def test_project_round_trip_preserves_joint_fingerprint_datum_and_shared_divider_role(tmp_path):
    from ae_engine.assembly_joint import (
        AssemblyJointRelation, migrate_legacy_snapshot_joints,
        resolved_joint_graph_fingerprint, set_part_edge_relation,
    )
    from ae_engine.door_dividers import derive_box_body_dividers, resolve_inner_door_lower_frame_role
    from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

    dividers = derive_box_body_dividers(
        [(800.0, [1100.0, 500.0])], depth=350.0, thickness=2.0,
        layout_scope="receiving-main",
    )
    role = resolve_inner_door_lower_frame_role("upper", dividers)
    assert role is not None
    state = migrate_legacy_snapshot_joints({
        "model": "受電箱", "assembly_type": "WRAP_OVERLAY",
        "existing_parts": ["box_body", "head", "tail", "door"],
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0, "fw": 29.0,
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "door_handle_edges": {"0:0": "RIGHT", "0:1": "RIGHT"},
        "door_nameplate_center_datum_top": 140.0,
        "inner_doors": [{
            "stable_id": "upper", "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
            "lower_frame_role": {"role": "lower_frame", "divider_stable_id": role.divider_stable_id},
        }],
    })
    state = set_part_edge_relation(state, "head", "LEFT", AssemblyJointRelation.WRAP)
    state = set_part_edge_relation(state, "head", "RIGHT", AssemblyJointRelation.OVERLAY)
    before_fp = resolved_joint_graph_fingerprint(state)
    path = tmp_path / "roundtrip.p6fold"
    write_project(path, {
        "schema": PROJECT_SCHEMA,
        "snapshot": state,
        "final_geometry": {},
    })
    loaded = read_project(path)["snapshot"]
    assert resolved_joint_graph_fingerprint(loaded) == before_fp
    assert loaded["door_nameplate_center_datum_top"] == pytest.approx(140.0)
    assert loaded["inner_doors"][0]["lower_frame_role"]["divider_stable_id"] == role.divider_stable_id
    assert loaded["door_handle_edges"] == {"0:0": "RIGHT", "0:1": "RIGHT"}


def test_nc_capability_is_explicit_and_does_not_fake_parallel_geometry():
    from ae_engine.manufacturing_api import resolved_manufacturing_nc_capability

    capability = resolved_manufacturing_nc_capability()
    assert capability["available"] is False
    assert "production NC sink" in capability["reason"]


def test_fold_designer_auto_syncs_receiving_divider_and_three_confirmed_frame_parts():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    from ae_engine.cabinet_types import receiving
    from fold_designer_bridge import Phase6FoldDesignerApp

    snap = receiving.apply_family_defaults({"t": 2.0})
    snap["existing_parts"] = ["box_body", "head", "tail", "door"]
    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = Phase6FoldDesignerApp(root, snap)
        divider_keys = [k for k in app.designer_workspace.available_parts if k.startswith("box_body:divider:")]
        frame_keys = {k for k in app.designer_workspace.available_parts if k.startswith("inner_door:")}
        assert divider_keys == ["box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"]
        assert frame_keys == {
            "inner_door:upper:top_frame",
            "inner_door:upper:left_frame",
            "inner_door:upper:right_frame",
        }
        assert app.designer_workspace.profiles_for("inner_door:upper:top_frame")["Y"][0]["len"] == pytest.approx(627.0)
        assert app.designer_workspace.profiles_for("inner_door:upper:left_frame")["Y"][0]["len"] == pytest.approx(1010.0)
        assert app.designer_workspace.profiles_for("inner_door:upper:right_frame")["Y"][0]["len"] == pytest.approx(1010.0)
        app.activate_part("inner_door:upper:top_frame")
        assert app.designer_workspace.active_part == "inner_door:upper:top_frame"
        assert app.part_var.get() == "上層內門上框"
        assert app.state.profiles["Y"][0]["len"] == pytest.approx(627.0)
        assert str(app.remove_part_button.cget("state")) == "disabled"

        app.activate_part("box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1")
        assert app.designer_workspace.active_part.startswith("box_body:divider:")
        assert app.part_var.get() == "箱身中隔（橫向）"
        assert str(app.remove_part_button.cget("state")) == "disabled"
    finally:
        try:
            if app is not None:
                app.root.destroy()
            else:
                root.destroy()
        except Exception:
            pass

def test_fold_designer_rederives_frame_spans_from_changed_multi_door_layout_without_saved_frame_spans():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    from ae_engine.cabinet_types import receiving
    from fold_designer_bridge import Phase6FoldDesignerApp

    snap = receiving.apply_family_defaults({"t": 2.0})
    snap["w"] = 820.0
    snap["door_layout_columns"] = [[820.0, [1000.0, 600.0]]]
    snap["existing_parts"] = ["box_body", "head", "tail", "door"]
    # No frame_spans are persisted as authoritative state.
    snap["inner_doors"][0].pop("frame_spans", None)
    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = Phase6FoldDesignerApp(root, snap)
        # Outer-door finished face: 820-(29+4)*2-7 = 747 wide;
        # 1000-(29+4)-7 = 960 high.  Then confirmed inner-door margins
        # remove 50 left/right/top, with the bottom landing on the divider.
        assert app.designer_workspace.profiles_for("inner_door:upper:top_frame")["Y"][0]["len"] == pytest.approx(647.0)
        assert app.designer_workspace.profiles_for("inner_door:upper:left_frame")["Y"][0]["len"] == pytest.approx(910.0)
        assert app.designer_workspace.profiles_for("inner_door:upper:right_frame")["Y"][0]["len"] == pytest.approx(910.0)

        # No stale frame_spans were saved; current topology is the only source.
        assert "frame_spans" not in snap["inner_doors"][0]
    finally:
        try:
            if app is not None:
                app.root.destroy()
            else:
                root.destroy()
        except Exception:
            pass

