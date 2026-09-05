# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from ae_engine.sheetmetal_geometry import CornerTypeId, resolve_corner_relief
from phase6_box_body_structure import BoxBodyStructureType, default_box_body_structure_state
from phase6_fold_profiles import (
    build_box_body_profile, build_endcap_xy_profiles, build_linked_endcap_xy_profiles,
    engine_segment_length_to_ui,
)


def _receiving_snapshot(**overrides):
    data = {
        "model": "受電箱",
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0, "fw": 29.0,
        "zl1": 24.0, "zl2": 24.0, "zr1": 17.0, "zr2": 18.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
    }
    data.update(overrides)
    return data


def test_receiving_family_defaults_are_explicit_and_do_not_reuse_vault_defaults():
    from ae_engine.cabinet_types.receiving import apply_family_defaults

    result = apply_family_defaults({"model": "受電箱", "h": 900.0, "t": 2.0})
    assert result["model"] == "受電箱"
    assert "cabinet_type" not in result
    assert result["w"] == 800.0
    assert result["d"] == 350.0
    assert result["fw"] == 29.0
    assert result["zl1"] == 24.0
    assert result["zl2"] == 24.0
    assert result["zr2"] == 18.0
    assert result["door_fold_l"] == 19.0
    assert result["door_fold_r"] == 19.0
    assert result["door_fold_t"] == 19.0
    assert result["door_fold_b"] == 19.0
    assert result["door_gap_w"] == 3.5
    assert result["door_gap_h"] == 3.5
    assert result["h"] == 1600.0
    assert result["t"] == 2.0


def test_receiving_box_body_profile_removes_zr1_and_keeps_dwd_core():
    profile = build_box_body_profile(_receiving_snapshot())
    keys = [row.get("phase6_key") for row in profile]
    assert keys == ["zl1", "zl2", "fw_left", "d_left", "w", "d_right", "fw_right", "zr2"]
    assert [row.get("core") for row in profile if row.get("core")] == ["D", "W", "D"]
    assert profile[-1].get("angle") is None
    # Receiving defaults are operator OUTSIDE dimensions, while Fold Profile
    # ``len`` is canonical MATERIAL length.  Each real adjacent bend removes
    # 1T from the material span; presentation metadata restores the UI values.
    assert [row["len"] for row in profile] == [22, 20, 25, 346, 796, 346, 25, 16]
    assert [engine_segment_length_to_ui(row) for row in profile] == [24, 24, 29, 350, 800, 350, 29, 18]


def test_receiving_canonical_box_topology_keeps_one_endcap_top_fold_not_zl1_zl2_copies():
    snapshot = _receiving_snapshot()
    box_profile = build_box_body_profile(snapshot)

    linked = build_linked_endcap_xy_profiles(snapshot, box_profile)
    head_y = linked["head"]["Y"]
    tail_y = linked["tail"]["Y"]

    assert [row.get("phase6_key") for row in head_y] == [
        "ytop1", "fw", "endcap_d_core", "ybottom1",
    ]
    assert [row.get("phase6_key") for row in tail_y] == [
        "ybottom1", "endcap_d_core", "fw", "ytop1",
    ]
    assert not any(
        str(row.get("phase6_key") or "").startswith("box_mating:")
        for rows in (head_y, tail_y) for row in rows
    )
    assert [row["len"] for row in head_y] == pytest.approx([16.0, 25.0, 346.0, 15.0])
    assert [row["len"] for row in tail_y] == pytest.approx([15.0, 346.0, 25.0, 16.0])


@pytest.mark.parametrize("part_key", ["head", "tail"])
def test_receiving_canonical_linked_top_uses_standard_insert_overlay_relief_not_40x23(part_key):
    from ae_engine import manufacturing_api
    from ae_engine.cabinet_types import receiving
    from ae_engine.certified_relief_registry import lookup_certified_endcap_relief
    from ae_engine.contracts import EndCapPartSpec
    from phase6_fold_profiles import profile_to_fold_segments

    snapshot = _receiving_snapshot(assembly_type="INSERT_OVERLAY")
    box_profile = build_box_body_profile(snapshot)
    profiles = build_linked_endcap_xy_profiles(snapshot, box_profile)[part_key]
    policy = receiving.endcap_corner_policy(
        frame_width=29.0, thickness=2.0, side_rear_bend=15.0,
    )
    render = manufacturing_api.build_part_render_data(EndCapPartSpec(
        width=800.0, height=1600.0, depth=350.0, thickness=2.0, frame_width=29.0,
        model_name="受電箱", is_tail=(part_key == "tail"),
        fold_left=15.0, fold_right=15.0, fold_top=16.0, fold_bottom=15.0,
        box_fold_left=24.0, box_fold_right=18.0,
        fold_profile_x=profile_to_fold_segments(profiles["X"]),
        fold_profile_y=profile_to_fold_segments(profiles["Y"]),
        corner_policy=policy, depth_comp_t=2.0,
    ))

    result = lookup_certified_endcap_relief(
        assembly_intent=CornerTypeId.INSERT_OVERLAY,
        endcap_render_data=render,
        box_body_x_profile=box_profile,
        endcap_x_profile=profiles["X"],
        endcap_y_profile=profiles["Y"],
        sheet_thickness=2.0,
        cabinet_family="受電箱",
        joint_face="TOP",
        joint_signature_relations=("INSERT_OVERLAY",),
    )

    assert result is not None
    assert result.rule_id == "ENDCAP_TOP_INSERT_OVERLAY_STANDARD_V1"
    for item in result.corner_reliefs:
        assert item.measurement.primary_u == pytest.approx(40.0)
        assert item.measurement.primary_v == pytest.approx(39.0)
        assert item.measurement.secondary_u == pytest.approx(16.0)
        assert item.measurement.secondary_depth == pytest.approx(4.0)


def test_receiving_forces_existing_side_back_structure_with_15mm_rear_bend():
    from ae_engine.cabinet_types.receiving import resolve_box_body_structure_state

    state = default_box_body_structure_state()
    result = resolve_box_body_structure_state(state)
    assert result["active_type"] == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    assert result["locked"] is True
    cfg = result["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    assert cfg["side_rear_bend"] == 15.0


def test_receiving_endcap_y_core_keeps_material_and_outside_dimension_spaces_separate():
    profile = build_endcap_xy_profiles(_receiving_snapshot(), part_key="head")["Y"]
    core = next(row for row in profile if row.get("phase6_key") == "endcap_d_core")
    # Root production contract: global D is outside 350; receiving EndCap
    # material core is D-2T = 346.  The two adjacent bends add 2T only for
    # operator presentation, so the editor-facing segment is 350.
    assert core["len"] == pytest.approx(346.0)
    assert core["ui_len_add"] == pytest.approx(4.0)
    assert engine_segment_length_to_ui(core) == pytest.approx(350.0)


def test_receiving_bottom_standard_uses_side_rear_bend_plus_1t_as_effective_fw_only():
    from ae_engine.cabinet_types.receiving import endcap_corner_policy

    policy = endcap_corner_policy(frame_width=29.0, thickness=2.0, side_rear_bend=15.0)
    assert policy.top_left.type_id is CornerTypeId.INSERT_OVERLAY
    assert policy.top_left.amount_t == 1.0
    # Receiving bottom owns only the STANDARD mother geometry. INSERT/WRAP
    # belongs to the resolved AssemblyJoint Graph / Certified Registry.
    assert policy.bottom_left.type_id is CornerTypeId.CROSS
    assert policy.bottom_left.cross_mode.value == "standard"
    assert policy.fw == 29.0
    assert policy.bottom_fw == pytest.approx(17.0)

    relief = resolve_corner_relief(
        policy.bottom_left,
        fold_u=15.0,
        fold_v=15.0,
        thickness=2.0,
        fw=policy.fw_for("bottom_left"),
    )
    assert relief.primary_u == pytest.approx(15.0)
    assert relief.primary_v == pytest.approx(15.0)
    assert relief.secondary_u is None
    assert relief.secondary_depth is None


def test_receiving_endcap_structural_depth_uses_d_minus_2t():
    from ae_engine.sheetmetal_part_adapters import build_unknown_endcap_result
    from ae_engine.cabinet_types.receiving import endcap_corner_policy, endcap_depth_comp_t

    result = build_unknown_endcap_result(
        w=800.0, d=350.0, t=2.0, fw=29.0,
        yl1=15.0, yr1=15.0, ytop1=16.0, ybottom1=15.0,
        corner_policy=endcap_corner_policy(frame_width=29.0, thickness=2.0, side_rear_bend=15.0),
        x_topology="folded", depth_comp_t=endcap_depth_comp_t(),
    )
    assert result.height == pytest.approx(350.0 - 4.0 + 16.0 + 29.0 + 15.0)


def test_receiving_model_switch_applies_family_defaults_structure_and_bottom_corner_policy(monkeypatch):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        vault_before = {
            key: var.get() for key, var in {
                "w": app.w_var, "d": app.d_var, "fw": app.fw_z_var,
                "zr1": app.zr1_var, "door_r": app.door_fold_r_var,
            }.items()
        }
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: None)
        app.baseline_var.set("受電箱")
        assert app.w_var.get() == "800"
        assert app.d_var.get() == "350"
        assert app.fw_z_var.get() == "29"
        assert app.zl1_var.get() == "24"
        assert app.zl2_var.get() == "24"
        assert app.zr2_var.get() == "18"
        assert [app.door_fold_l_var.get(), app.door_fold_r_var.get(), app.door_fold_t_var.get(), app.door_fold_b_var.get()] == ["19"] * 4
        structure = app.workspace_controller.box_body_structure_state()
        assert structure["active_type"] == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
        bottom = app.manual_corner_state["head"]["bottom_left"]
        assert bottom.type_id is CornerTypeId.CROSS
        assert bottom.cross_mode.value == "standard"
        from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part
        assert edge_relation_for_part(app.assembly_joint_state, "head", "BOTTOM") is AssemblyJointRelation.WRAP
        app._inherit_known_corner_state_into_custom()
        inherited_bottom = app.manual_corner_state["head"]["bottom_left"]
        assert inherited_bottom.type_id is CornerTypeId.CROSS
        assert inherited_bottom.cross_mode.value == "standard"

        app.baseline_var.set("金庫型")
        assert app.w_var.get() == vault_before["w"]
        assert app.d_var.get() == vault_before["d"]
        assert app.fw_z_var.get() == vault_before["fw"]
        assert app.zr1_var.get() == vault_before["zr1"]
        assert app.door_fold_r_var.get() == vault_before["door_r"]
    finally:
        root.destroy()


def test_receiving_gui_part_specs_drive_actual_2d_contracts_and_survive_snapshot_restore(monkeypatch):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: None)
        app.baseline_var.set("受電箱")
        val = app.get_float_values()

        box_spec = app._box_body_part_spec(val)
        keys = [row.phase6_key for row in box_spec.fold_profile]
        assert keys == ["zl1", "zl2", "fw_left", "d_left", "w", "d_right", "fw_right", "zr2"]
        assert box_spec.structure_state["active_type"] == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
        box_render = app._authoritative_render_data(box_spec)
        assert [piece.role for piece in box_render.pieces] == ["left_side", "back", "right_side"]

        head_spec = app._end_cap_part_spec(val, is_tail=False)
        assert head_spec.depth_comp_t == pytest.approx(2.0)
        assert head_spec.corner_policy.bottom_fw == pytest.approx(17.0)
        assert head_spec.corner_policy.bottom_left.type_id is CornerTypeId.CROSS
        assert head_spec.corner_policy.bottom_left.cross_mode.value == "standard"
        structure = app.workspace_controller.box_body_structure_state()
        structure["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]["side_rear_bend"] = 20.0
        app.workspace_controller.set_box_body_structure_state(structure)
        assert app._end_cap_part_spec(val, is_tail=False).corner_policy.bottom_fw == pytest.approx(22.0)
        structure["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]["side_rear_bend"] = 15.0
        app.workspace_controller.set_box_body_structure_state(structure)
        head_render = app._authoritative_render_data(head_spec)
        _minx, miny, _maxx, maxy = map(float, head_render.material.bounds)
        # Canonical blank uses MATERIAL lengths: ytop1=16 + FW(29 outside - 2T)=25
        # + D-core(350 - 2T)=346 + ybottom1=15 = 402.  The previous 406 oracle
        # accidentally locked the duplicated zl1/zl2 linked-chain bug.
        assert maxy - miny == pytest.approx(402.0)

        door_spec = app._single_door_part_spec(val)
        assert (
            door_spec.fold_left, door_spec.fold_right, door_spec.fold_top, door_spec.fold_bottom
        ) == pytest.approx((19.0, 19.0, 19.0, 19.0))
        assert (door_spec.gap_w, door_spec.gap_h) == pytest.approx((3.5, 3.5))

        snapshot = app._compose_phase6_project_snapshot_from_main_gui()
    finally:
        root.destroy()

    root2 = tk.Tk(); root2.withdraw()
    restored = gui.BoxCalculatorGUI(root2)
    try:
        restored._apply_phase6_project_snapshot(snapshot)
        assert restored.baseline_var.get() == "受電箱"
        assert restored._active_cabinet_type == "受電箱"
        restored_val = restored.get_float_values()
        restored_head = restored._end_cap_part_spec(restored_val, is_tail=False)
        restored_head_profile = restored.workspace_controller.profile_for("head") or {}
        restored_core = next(
            row for row in restored_head_profile.get("Y", ())
            if row.get("phase6_key") == "endcap_d_core"
        )
        assert restored_core["len"] == pytest.approx(346.0)
        assert restored_head.depth_comp_t == pytest.approx(2.0)
        assert restored_head.corner_policy.bottom_fw == pytest.approx(17.0)
        assert "下方：包覆貼外" in restored._fixed_corner_summary("head")
        assert "BOTTOM＝WRAP" in restored._fixed_corner_summary("head")
    finally:
        root2.destroy()


def test_switching_from_vault_discards_stale_endcap_fold_profiles_for_receiving_family(monkeypatch):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        vault_snapshot = app._make_original_fold_designer_snapshot()
        vault_head = build_endcap_xy_profiles(vault_snapshot, part_key="head")
        workspace = app.workspace_controller.workspace_snapshot()
        workspace["existing_parts"] = list(dict.fromkeys([*workspace["existing_parts"], "head", "tail"]))
        workspace["part_profiles"] = {"head": vault_head, "tail": build_endcap_xy_profiles(vault_snapshot, part_key="tail")}
        app.workspace_controller.commit_workspace(workspace)
        vault_core = next(row for row in vault_head["Y"] if row.get("phase6_key") == "endcap_d_core")
        assert vault_core["len"] != 346

        monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: None)
        app.baseline_var.set("受電箱")
        receiving_head = app.workspace_controller.profile_for("head") or {}
        receiving_core = next(
            row for row in receiving_head.get("Y", ()) if row.get("phase6_key") == "endcap_d_core"
        )
        assert receiving_core["len"] == pytest.approx(346.0)
    finally:
        root.destroy()


def test_receiving_fixed_corner_summary_projects_bottom_joint_relation(monkeypatch):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    from ae_engine.assembly_joint import AssemblyJointRelation, set_part_edge_relation

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: None)
        app.baseline_var.set("受電箱")
        summary = app._fixed_corner_summary("head")
        assert "下方：包覆貼外" in summary
        assert "BOTTOM＝WRAP" in summary

        app.assembly_joint_state = set_part_edge_relation(
            app.assembly_joint_state, "head", "BOTTOM", AssemblyJointRelation.WRAP,
        )
        wrapped = app._fixed_corner_summary("head")
        assert "下方：包覆貼外" in wrapped
        assert "BOTTOM＝WRAP" in wrapped
    finally:
        try:
            root.destroy()
        except Exception:
            pass
