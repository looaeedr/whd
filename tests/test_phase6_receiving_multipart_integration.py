from __future__ import annotations

import os

import pytest

from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2


def _feature(diameter: float, x: float):
    return CircleFeature(
        diameter=diameter,
        anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(x, 0.0),
        layer="CUTTING",
        source_type="t08",
    )


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_opening_receiving_designer_preserves_formal_door_features_and_authoritative_rows():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        upper = _feature(12.0, -20.0)
        lower = _feature(18.0, 30.0)
        app.surface_features["door_c1_r1"] = [upper]
        app.surface_features["door_c1_r2"] = [lower]

        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        wanted = tuple(designer.designer_workspace.available_parts)
        assert "door" not in wanted
        assert "door_c1_r1" in wanted and "door_c1_r2" in wanted
        assert any(key.startswith("box_body:divider:") for key in wanted)
        assert {
            "inner_door:upper:top_frame",
            "inner_door:upper:left_frame",
            "inner_door:upper:right_frame",
        }.issubset(wanted)
        assert tuple(designer.assembly_part_formed_vars) == wanted
        assert tuple(designer.assembly_part_blank_vars) == wanted
        assert tuple(designer.assembly_part_corner_vars) == wanted
        assert designer.designer_workspace.features_for("door_c1_r1") == [upper]
        assert designer.designer_workspace.features_for("door_c1_r2") == [lower]
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass


def _open_receiving_t08():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = app.open_original_fold_designer()
    root.update_idletasks(); root.update()
    designer.baseline_model_var.set("受電箱")
    root.update_idletasks(); root.update()
    designer.structure_type_var.set("三件式（側背分離）")
    bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
    root.update_idletasks(); root.update()
    return tk, root, app, designer, bridge


def _destroy_t08(tk, root, designer=None):
    try:
        if designer is not None:
            designer.root.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except tk.TclError:
        pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_joint_shrinks_features_round_trip_from_designer_to_project(tmp_path):
    import gui
    import phase6_project_file as project
    from ae_engine.assembly_joint import edge_relation_for_part

    tk, root, app, designer, bridge = _open_receiving_t08()
    path = tmp_path / "receiving-multipart-t08.p6fold"
    upper = _feature(12.0, -20.0)
    lower = _feature(18.0, 30.0)
    edge = None
    changed_relation = None
    try:
        bridge._phase6_query_assembly_render_data(designer)
        assert tuple(designer.assembly_box_body_piece_formed_vars) == (
            "box_body:left_side", "box_body:back", "box_body:right_side",
        )

        designer.activate_part("head")
        root.update_idletasks(); root.update()
        edge = next(edge for edge, allowed in designer.endcap_joint_allowed.items() if len(allowed) > 1)
        current_label = designer.endcap_joint_vars[edge].get()
        alternate = next(value for value in designer.endcap_joint_allowed[edge] if value != current_label)
        designer.endcap_joint_vars[edge].set(alternate)
        bridge._phase6_on_endcap_edge_relation_selected(designer, "head", edge)
        changed_relation = edge_relation_for_part(designer._phase6_input_snapshot, "head", edge)

        designer.activate_part("base_plate")
        root.update_idletasks(); root.update()
        for shrink_edge, value in {"TOP": 11, "BOTTOM": 22, "LEFT": 33, "RIGHT": 44}.items():
            assert bridge._phase6_commit_base_plate_edge_shrink(designer, shrink_edge, str(value))

        designer.designer_workspace.stash_features("door_c1_r1", [upper])
        designer.designer_workspace.stash_features("door_c1_r2", [lower])
        designer._phase6_last_live_fingerprint = None
        assert bridge._phase6_publish_live_state(designer, force=True) is True
        root.update_idletasks(); root.update()

        snap = app._compose_phase6_project_snapshot_from_main_gui()
        assert edge_relation_for_part(snap, "head", edge) == changed_relation
        assert snap["base_plate_shrink_top"] == pytest.approx(11)
        assert snap["base_plate_shrink_bottom"] == pytest.approx(22)
        assert snap["base_plate_shrink_left"] == pytest.approx(33)
        assert snap["base_plate_shrink_right"] == pytest.approx(44)
        assert snap["part_features"]["door_c1_r1"] == [upper]
        assert snap["part_features"]["door_c1_r2"] == [lower]
        project.write_project(path, {
            "schema": project.PROJECT_SCHEMA,
            "saved_at": "2026-09-04T21:00:00+08:00",
            "snapshot": snap,
            "final_geometry": {},
        })
    finally:
        _destroy_t08(tk, root, designer)

    root2 = tk.Tk(); root2.withdraw(); app2 = gui.BoxCalculatorGUI(root2); designer2 = None
    try:
        designer2 = app2.load_phase6_project(path, open_designer=True)
        root2.update_idletasks(); root2.update()
        assert edge_relation_for_part(designer2._phase6_input_snapshot, "head", edge) == changed_relation
        assert designer2._settings_values["base_plate_shrink_top"] == pytest.approx(11)
        assert designer2._settings_values["base_plate_shrink_bottom"] == pytest.approx(22)
        assert designer2._settings_values["base_plate_shrink_left"] == pytest.approx(33)
        assert designer2._settings_values["base_plate_shrink_right"] == pytest.approx(44)
        assert designer2.designer_workspace.features_for("door_c1_r1") == [upper]
        assert designer2.designer_workspace.features_for("door_c1_r2") == [lower]
    finally:
        _destroy_t08(tk, root2, designer2)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_drawing_edge_hosts_keep_place_ownership_across_resize_and_fullscreen():
    tk, root, app, designer, bridge = _open_receiving_t08()
    try:
        designer.activate_part("head")
        for geometry in ("960x680", "1280x820"):
            designer.root.geometry(geometry)
            root.update_idletasks(); root.update()
            canvas = designer.renderer.canvas.get_tk_widget()
            cx1, cy1 = canvas.winfo_rootx(), canvas.winfo_rooty()
            cx2, cy2 = cx1 + canvas.winfo_width(), cy1 + canvas.winfo_height()
            for host in (
                designer.drawing_edge_hosts.top, designer.drawing_edge_hosts.bottom,
                designer.drawing_edge_hosts.left, designer.drawing_edge_hosts.right,
            ):
                x1, y1 = host.winfo_rootx(), host.winfo_rooty()
                x2, y2 = x1 + host.winfo_width(), y1 + host.winfo_height()
                assert host.winfo_manager() == "place"
                assert cx1 <= x1 <= x2 <= cx2
                assert cy1 <= y1 <= y2 <= cy2

        bridge._phase6_toggle_fullscreen(designer)
        root.update_idletasks(); root.update()
        assert all(host.winfo_manager() == "place" for host in (
            designer.drawing_edge_hosts.top, designer.drawing_edge_hosts.bottom,
            designer.drawing_edge_hosts.left, designer.drawing_edge_hosts.right,
        ))
        if designer._phase6_fullscreen:
            bridge._phase6_toggle_fullscreen(designer)
    finally:
        _destroy_t08(tk, root, designer)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_multipart_project_round_trip_preserves_joints_shrinks_features_and_piece_identity(tmp_path):
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    import phase6_project_file as project
    from ae_engine.assembly_joint import (
        AssemblyJointRelation,
        edge_relation_for_part,
        set_part_edge_relation,
    )
    from phase6_box_body_structure import BoxBodyStructureType

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    root2 = None
    app2 = None
    designer2 = None
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        for var, value in (
            (app.base_plate_shrink_top_var, "11"),
            (app.base_plate_shrink_bottom_var, "22"),
            (app.base_plate_shrink_left_var, "33"),
            (app.base_plate_shrink_right_var, "44"),
        ):
            var.set(value)
        app.assembly_joint_state = set_part_edge_relation(
            app.assembly_joint_state, "head", "LEFT", AssemblyJointRelation.WRAP
        )
        app.assembly_joint_state = set_part_edge_relation(
            app.assembly_joint_state, "tail", "RIGHT", AssemblyJointRelation.OVERLAY
        )
        upper = _feature(12.0, -20.0)
        lower = _feature(18.0, 30.0)
        app.surface_features["door_c1_r1"] = [upper]
        app.surface_features["door_c1_r2"] = [lower]

        snapshot = app._compose_phase6_project_snapshot_from_main_gui()
        path = tmp_path / "receiving_t08_roundtrip.p6fold"
        project.write_project(path, {
            "schema": project.PROJECT_SCHEMA,
            "saved_at": "2026-09-04T20:00:00+08:00",
            "snapshot": snapshot,
            "final_geometry": {},
        })
        loaded = project.read_project(path)["snapshot"]

        root2 = tk.Tk(); root2.withdraw(); app2 = gui.BoxCalculatorGUI(root2)
        app2._apply_phase6_project_snapshot(loaded)
        root2.update_idletasks(); root2.update()
        assert app2.baseline_var.get() == "受電箱"
        assert app2.workspace_controller.box_body_structure_state()["active_type"] == (
            BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
        )
        assert app2.get_door_layout_columns() == [(800.0, [1100.0, 500.0])]
        assert app2.surface_features["door_c1_r1"] == [upper]
        assert app2.surface_features["door_c1_r2"] == [lower]
        assert edge_relation_for_part(app2.assembly_joint_state, "head", "LEFT") is AssemblyJointRelation.WRAP
        assert edge_relation_for_part(app2.assembly_joint_state, "tail", "RIGHT") is AssemblyJointRelation.OVERLAY
        assert [
            float(app2.base_plate_shrink_top_var.get()),
            float(app2.base_plate_shrink_bottom_var.get()),
            float(app2.base_plate_shrink_left_var.get()),
            float(app2.base_plate_shrink_right_var.get()),
        ] == pytest.approx([11.0, 22.0, 33.0, 44.0])

        designer2 = app2.open_original_fold_designer()
        root2.update_idletasks(); root2.update()
        bridge._phase6_query_assembly_render_data(designer2)
        root2.update_idletasks(); root2.update()

        wanted = tuple(designer2.designer_workspace.available_parts)
        assert tuple(designer2.assembly_part_formed_vars) == wanted
        assert tuple(designer2.assembly_part_blank_vars) == wanted
        assert tuple(designer2.assembly_part_corner_vars) == wanted
        assert tuple(designer2.assembly_box_body_piece_formed_vars) == (
            "box_body:left_side", "box_body:back", "box_body:right_side"
        )
        for key in designer2.assembly_box_body_piece_formed_vars:
            assert "等待3D" not in designer2.assembly_box_body_piece_formed_vars[key].get()
            assert "等待3D" not in designer2.assembly_box_body_piece_blank_vars[key].get()
        assert designer2.designer_workspace.features_for("door_c1_r1") == [upper]
        assert designer2.designer_workspace.features_for("door_c1_r2") == [lower]
        resolved = bridge._phase6_resolve_manufacturing_geometry(designer2)
        resolved_keys = tuple(part.part_key for part in resolved.parts)
        assert resolved_keys == wanted
        assert resolved.part("door_c1_r1").offset != resolved.part("door_c1_r2").offset
    finally:
        try:
            if designer2 is not None:
                designer2.root.destroy()
        except Exception:
            pass
        try:
            if root2 is not None:
                root2.destroy()
        except Exception:
            pass
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass
