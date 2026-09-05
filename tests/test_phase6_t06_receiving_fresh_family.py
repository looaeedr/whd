from __future__ import annotations

import os

import pytest


def test_receiving_family_defaults_publish_fresh_intent_layout_and_upper_inner_door_role():
    from ae_engine.cabinet_types.receiving import apply_family_defaults, derive_inner_door_frame_sets
    from ae_engine.door_dividers import derive_box_body_dividers

    result = apply_family_defaults({"model": "金庫型", "w": 400, "h": 600, "d": 250, "t": 2, "fw": 29})
    assert (result["w"], result["h"], result["d"], result["fw"]) == (800.0, 1600.0, 350.0, 29.0)
    assert result["assembly_type"] == "WRAP_OVERLAY"
    assert result["multi_door_enabled"] is True
    assert result["door_layout_columns"] == [[800.0, [1100.0, 500.0]]]
    assert (result["door_fold_t"], result["door_fold_b"], result["door_fold_l"], result["door_fold_r"]) == (19.0, 19.0, 19.0, 19.0)

    # Only the upper cell has an inner door.  Its bottom-frame role is the
    # canonical box-body divider; no inner-door-only bottom frame is requested.
    assert len(result["inner_doors"]) == 1
    inner = result["inner_doors"][0]
    assert inner["stable_id"] == "upper"
    assert inner["cell_key"] == "0:0"
    assert inner["included_frame_sides"] == ["top", "left", "right"]
    # The inner door is sized from the upper outer-door finished face.  Door
    # gaps are already removed by the Door resolver, then the confirmed frame
    # margins subtract another 50 mm on left/right/top.  Bottom is the shared
    # divider, so there is no independent bottom-frame span.
    frame_sets = derive_inner_door_frame_sets(result)
    assert len(frame_sets) == 1
    assert frame_sets[0].inner_door_id == "upper"
    assert frame_sets[0].included_sides == ("top", "left", "right")
    assert frame_sets[0].spans == {
        "top": pytest.approx(627.0),
        "left": pytest.approx(1010.0),
        "right": pytest.approx(1010.0),
    }
    # Frame spans are derived mechanical data, not duplicate project authority.
    assert "frame_spans" not in inner
    dividers = derive_box_body_dividers(
        [(800.0, [1100.0, 500.0])], depth=350.0, thickness=2.0,
        layout_scope=result["door_layout_scope"],
    )
    assert len(dividers) == 1
    assert inner["lower_frame_role"] == {
        "role": "lower_frame",
        "divider_stable_id": dividers[0].stable_id,
    }


def test_receiving_structure_is_still_locked_side_back_split():
    from ae_engine.cabinet_types.receiving import resolve_box_body_structure_state
    from phase6_box_body_structure import BoxBodyStructureType

    state = resolve_box_body_structure_state()
    assert state["active_type"] == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    assert state["locked"] is True


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_main_gui_fresh_receiving_switch_sets_wrap_overlay_and_1100_500_layout():
    import tkinter as tk
    import gui
    from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        assert (float(app.w_var.get()), float(app.h_var.get()), float(app.d_var.get())) == (800.0, 1600.0, 350.0)
        assert app._current_box_assembly_type() == "WRAP_OVERLAY"
        for part in ("head", "tail"):
            assert edge_relation_for_part(app.assembly_joint_state, part, "TOP") is AssemblyJointRelation.OVERLAY
            assert edge_relation_for_part(app.assembly_joint_state, part, "BOTTOM") is AssemblyJointRelation.WRAP
            assert edge_relation_for_part(app.assembly_joint_state, part, "LEFT") is AssemblyJointRelation.INSERT
            assert edge_relation_for_part(app.assembly_joint_state, part, "RIGHT") is AssemblyJointRelation.INSERT
        assert app.multi_door_enabled_var.get() is True
        assert app.get_door_layout_columns() == [(800.0, [1100.0, 500.0])]
        assert len(app.receiving_inner_doors) == 1
        assert app.receiving_inner_doors[0]["cell_key"] == "0:0"
        assert "bottom" not in app.receiving_inner_doors[0]["included_frame_sides"]
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_family_round_trip_keeps_explicit_runtime_overrides():
    import tkinter as tk
    import gui
    from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part, set_part_edge_relation

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        app.w_var.set("820")
        app.set_door_layout_columns([(820, [1000, 600])])
        app.assembly_joint_state = set_part_edge_relation(
            app.assembly_joint_state, "head", "LEFT", AssemblyJointRelation.WRAP
        )

        app.baseline_var.set("金庫型")
        root.update_idletasks(); root.update()
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()

        assert float(app.w_var.get()) == 820.0
        assert app.get_door_layout_columns() == [(820.0, [1000.0, 600.0])]
        assert edge_relation_for_part(app.assembly_joint_state, "head", "LEFT") is AssemblyJointRelation.WRAP
        assert edge_relation_for_part(app.assembly_joint_state, "head", "BOTTOM") is AssemblyJointRelation.WRAP
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_fold_designer_fresh_receiving_switch_materializes_wrap_overlay_graph():
    import tkinter as tk
    import gui
    from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()
        assert designer._phase6_input_snapshot["assembly_type"] == "WRAP_OVERLAY"
        assert designer.assembly_type_var.get() == "包覆貼外"
        assert edge_relation_for_part(designer._phase6_input_snapshot, "head", "BOTTOM") is AssemblyJointRelation.WRAP
        assert edge_relation_for_part(designer._phase6_input_snapshot, "tail", "BOTTOM") is AssemblyJointRelation.WRAP
        assert designer._phase6_input_snapshot["door_layout_columns"] == [[800.0, [1100.0, 500.0]]]
        assert len(designer._phase6_input_snapshot["inner_doors"]) == 1
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass

@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_saved_receiving_project_values_win_over_fresh_family_defaults():
    import tkinter as tk
    import gui
    from ae_engine.assembly_joint import edge_relation_for_part, AssemblyJointRelation, migrate_legacy_snapshot_joints
    from ae_engine.cabinet_types.receiving import resolve_box_body_structure_state

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        snapshot = app._compose_phase6_project_snapshot_from_main_gui()
        snapshot["model"] = "受電箱"
        snapshot["assembly_type"] = "OVERLAY"
        snapshot.update({"w": 910.0, "h": 1710.0, "d": 365.0, "fw": 31.0})
        snapshot["settings"].update({"w": 910.0, "h": 1710.0, "d": 365.0, "fw": 31.0})
        graph = migrate_legacy_snapshot_joints({
            "assembly_type": "OVERLAY",
            "existing_parts": ["box_body", "head", "tail"],
        })
        snapshot["assembly_joint_schema_version"] = graph["assembly_joint_schema_version"]
        snapshot["assembly_joints"] = graph["assembly_joints"]
        snapshot["workspace"]["box_body_structure"] = resolve_box_body_structure_state(
            snapshot["workspace"].get("box_body_structure")
        )

        app._apply_phase6_project_snapshot(snapshot)
        root.update_idletasks(); root.update()
        assert (float(app.w_var.get()), float(app.h_var.get()), float(app.d_var.get()), float(app.fw_z_var.get())) == (910.0, 1710.0, 365.0, 31.0)
        assert app._current_box_assembly_type().value == "OVERLAY"
        assert edge_relation_for_part(app.assembly_joint_state, "head", "BOTTOM") is AssemblyJointRelation.INSERT
        assert app.workspace_controller.box_body_structure_state()["active_type"] == "three_piece_side_back_split"
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
