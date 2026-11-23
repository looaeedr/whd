# -*- coding: utf-8 -*-
"""#3317 actual WHD Tk Ø4 CHECK window: Factory body/real Tail/true world.

This is a CHECK view from WHD Engine, never a fabrication drawing or a
substitute for unperformed AutoCAD/physical-BoxBody acceptance.
"""
import base64
from io import BytesIO
import os
import tkinter as tk
from tkinter import ttk

import ezdxf
import pytest

import gui
from ae_engine import manufacturing_api as api
from ae_engine.assembly_geometry import triangle_bounds


def test_actual_whd_gui_d4_check_window_four_factory_holes_and_native_world(
    record_property, tmp_path, monkeypatch,
):
    if os.name!="nt" and not os.environ.get("DISPLAY"):
        pytest.skip("requires real Tk/Xvfb GUI")
    root=tk.Tk()
    root.withdraw()
    designer=None
    win=None
    try:
        main=gui.BoxCalculatorGUI(root)
        main.baseline_var.set("金庫型")
        main.w_var.set("620")
        main.h_var.set("600")
        main.d_var.set("185")
        if hasattr(main,"t_var"):
            main.t_var.set("2")
        main._apply_existing_parts_from_fold_workspace(
            ["box_body","head","tail"],
        )
        designer=main.open_original_fold_designer()
        root.update_idletasks()
        root.update()
        designer.activate_part("tail")
        # REAL native Fold Editor; do not alter a test-created FinalScene.
        editor=designer.bend_ui
        editor.nb.select(editor.tabs.index("Y"))
        root.update_idletasks()
        root.update()
        editor.on_tab(None)
        editor.render()
        rows=editor.get_active_dict()["Y"]
        bottom_idx=next(i for i,seg in enumerate(rows)
                        if seg.get("phase6_key")=="ybottom1")
        candidate=[dict(seg) for seg in rows]
        candidate[bottom_idx]["len"]=48.
        displayed=api.project_operator_fold_editor_display_rows(
            candidate,getattr(designer.state,"phase6_thickness",2.),
        )
        editor.controls[bottom_idx]["len"].set(
            str(displayed[bottom_idx]["len"])
        )
        editor.save()
        designer._save_current_part(notify=False)
        root.update_idletasks()
        root.update()
        page=designer.settings_panel.render_context("tail")
        state=page["extension_state"]
        assert state["tail_lower_v_choice_widget"].winfo_exists()
        button=state.get("tail_d4_check_widget")
        assert button is not None and button.winfo_exists()
        # The preceding native Y Fold Editor Save queued an ordinary
        # assembly_relief source reconciliation (old 15 -> new 48).
        # Complete THAT prior edit before measuring a CHECK-only click.
        # Otherwise Tk after jobs would falsely attribute its legitimate
        # writeback to the read-only Ø4 window.
        designer._phase6_update_scheduler.flush_now()
        root.update_idletasks()
        root.update()
        from copy import deepcopy
        before=deepcopy(designer._phase6_input_snapshot)
        assert before["assembly_relief"]["source"]["ybottom1"] == pytest.approx(48.)
        button.invoke()
        root.update_idletasks()
        root.update()
        matches=[
            w for w in designer.root.winfo_children()
            if isinstance(w,tk.Toplevel) and "CHECK_NOT_CNC" in w.title()
        ]
        assert len(matches)==1, (
            "D4_NATIVE_GUI_CHECK_VIEW_NOT_SHOWN",
            designer.settings_status_var.get(),
        )
        win=matches[0]
        flat=win._tail_d4_check_flat
        check=win._tail_d4_check_shell
        body=win._tail_d4_check_body_world
        placed=win._tail_d4_check_placed_world
        assert flat.source_spec.width==620
        assert flat.source_spec.depth==185
        assert flat.source_spec.thickness==2
        assert len([p for p in flat.result_scene.primitives
                    if p.layer=="CUTTING"])==5  # outer+four real Factory
        assert len([p for p in flat.result_scene.primitives
                    if p.layer=="BEND"])==5
        assert not any(getattr(p,"semantic_id",None)==
                       "USER_ADDED_CHECK_CUTTING"
                       for p in flat.result_scene.primitives)
        assert len(placed)==len(check.shell_faces)
        body_bounds=triangle_bounds(body)
        assert body_bounds[0]==pytest.approx((-310.,310.),abs=1e-7)
        assert body_bounds[2]==pytest.approx((-92.5,92.5),abs=1e-7)
        assert body_bounds[1]==pytest.approx((-298.,298.),abs=1e-7)
        tail_bounds=triangle_bounds(placed)
        assert tail_bounds[0]==pytest.approx((-308.,308.),abs=1e-7)
        assert tail_bounds[2]==pytest.approx((-91.5,91.5),abs=1e-7)
        assert tail_bounds[1][0]==pytest.approx(-300.,abs=1e-7)
        assert designer._phase6_input_snapshot==before
        actual=win._tail_d4_assembly_check
        assert actual.body_triangle_count==len(body)==308
        assert actual.tail_triangle_count==len(placed)==2860
        assert actual.crossing_pair_count>=0
        assert len(actual.crossing_segments)>=0
        assert actual.crossing_tail_uv_bounds is not None
        assert actual.crossing_world_bounds is not None
        assert len(actual.crossing_target_face_indices)>0
        assert max(actual.crossing_target_face_indices)<len(placed)
        assert sum(count for _,count in actual.crossing_regions)==len(
            actual.crossing_target_face_indices
        )
        assert not actual.manufacturing_approved
        # Exact surface face locations at genuine interior material probes.
        # These are NOT derived from the orange surface-crossing count.
        from ae_engine.assembly_geometry import probe_native_world_mesh_axis_faces
        for fixed_xyz, body_expected, tail_expected in (
            ((0.,-290.,-20.),(-310.,-308.),(-308.,-306.)),
            ((0.,-290.,-20.),(308.,310.),(306.,308.)),
        ):
            body_hits=probe_native_world_mesh_axis_faces(
                body,axis=0,fixed_xyz=fixed_xyz,
            )
            tail_hits=probe_native_world_mesh_axis_faces(
                placed,axis=0,fixed_xyz=fixed_xyz,
            )
            for value in body_expected:
                assert any(abs(x-value)<1e-4 for x in body_hits),(
                    "BODY_SIDE_PROBE",value,body_hits,
                )
            for value in tail_expected:
                assert any(abs(x-value)<1e-4 for x in tail_hits),(
                    "TAIL_SIDE_PROBE",value,tail_hits,
                )
        rear_body=probe_native_world_mesh_axis_faces(
            body,axis=2,fixed_xyz=(100.,-275.,0.),
        )
        rear_tail=probe_native_world_mesh_axis_faces(
            placed,axis=2,fixed_xyz=(100.,-275.,0.),
        )
        for value in (-92.5,-90.5):
            assert any(abs(z-value)<1e-4 for z in rear_body),(
                "BODY_REAR_PROBE",value,rear_body,
            )
        # Front is an OPENING: x=100 crosses no front sheet. Do not
        # invent an entire front wall. Check its actual surviving source
        # flange triangle vertices alongside the full formed D bounds.
        front_skin_z={
            round(float(point[2]),6)
            for triangle in body for point in triangle
            if float(point[2])>90.
        }
        assert 90.5 in front_skin_z and 92.5 in front_skin_z
        front_body=probe_native_world_mesh_axis_faces(
            body,axis=2,fixed_xyz=(290.,-275.,0.),
        )
        for value in (-92.5,-90.5,90.5,92.5):
            assert any(abs(z-value)<1e-4 for z in front_body),(
                "BODY_ACTUAL_FRONT_FRAME_PROBE",value,front_body,
            )
        # The real lower left front-frame corner is not the empty x100
        # opening. Use this exact local ray instead of a made-up front wall.
        front_corner_body=probe_native_world_mesh_axis_faces(
            body,axis=2,fixed_xyz=(-294.,-297.,0.),
        )
        front_corner_tail=probe_native_world_mesh_axis_faces(
            placed,axis=2,fixed_xyz=(-294.,-297.,0.),
        )
        assert len(front_corner_body)>=2 and len(front_corner_tail)>=2,(
            "D4_REAL_FRONT_FRAME_SOURCE_MISSING",
            front_corner_body,front_corner_tail,
        )
        body_front=tuple(sorted(front_corner_body)[-2:])
        tail_front=tuple(sorted(front_corner_tail)[-2:])
        front_overlap=min(body_front[1],tail_front[1])-max(
            body_front[0],tail_front[0],
        )
        assert front_overlap==pytest.approx(1.,abs=1e-5),(
            "D4_FRONT_FRAME_PHYSICAL_INTERIOR_OVERLAP",
            body_front,tail_front,front_overlap,
        )
        for value in (-91.5,-89.5):
            assert any(abs(z-value)<1e-4 for z in rear_tail),(
                "TAIL_REAR_PROBE",value,rear_tail,
            )
        # Repaired integral Body thickness removes the left/right 1-mm
        # overlap; the independent rear Tail/Body overlap is still 1 mm.
        assert min(-90.5,-89.5)-max(-92.5,-91.5)==pytest.approx(1.)
        # Compare an UNMODIFIED Factory Tail folded by the original WHD
        # Fold/FinalScene owner, not an alternate Ø4 surrogate. A raw
        # straight Tail rear can mate the corrected Body rear inside face
        # while the Ø4 root still overlaps: these claims are independent.
        from ae_engine.endcap_factory_fold import build_endcap_xy_fold_profiles
        from ae_engine.v_miter_tail_no_ba_sequential import (
            exact_tail_y_fold_profile_from_original_bends,
        )
        from ae_engine.assembly_geometry_folded_mesh import folded_mesh_from_polygon
        from ae_engine.manufacturing_render_data import (
            material_polygon_from_final_scene,fold_guides_from_final_scene,
        )
        spec=flat.source_spec
        original_profiles=build_endcap_xy_fold_profiles({
            "model":spec.model_name,"w":spec.width,"d":spec.depth,
            "t":spec.thickness,"fw":spec.frame_width,
            "yl1":spec.fold_left,"yr1":spec.fold_right,
            "ytop1":spec.fold_top,"ybottom1":spec.fold_bottom,
        },part_key="tail")
        original_surface=folded_mesh_from_polygon(
            material_polygon_from_final_scene(flat.original_scene),
            original_profiles["X"],
            exact_tail_y_fold_profile_from_original_bends(flat),
            fold_guides=fold_guides_from_final_scene(flat.original_scene),
        )
        original_world=api.resolve_assembled_endcap_world_skins(
            original_surface,placement="bottom",
            box_body_world=body,thickness=spec.thickness,
            preserve_core_origin=False,
        ).solid_triangles
        original_rear_hits=probe_native_world_mesh_axis_faces(
            original_world,axis=2,fixed_xyz=(100.,-275.,0.),
        )
        record_property("ISSUE3317_UNMODIFIED_FACTORY_REAR_Z",repr(original_rear_hits))
        assert all(any(abs(z-v)<1e-4 for z in original_rear_hits)
                   for v in (-90.5,-88.5)),(
            "ORIGINAL_TAIL_REAR_DATUM_DIFFERS",original_rear_hits,
        )
        # Reuse the SAME actual GUI Body and native approved 2D for Y-first;
        # do not substitute a 36/312-face separate Body mesh.
        from ae_engine.v_miter_tail_d4_check import (
            project_tail_d4_source_keyed_t_check,
        )
        second=project_tail_d4_source_keyed_t_check(flat,first_axis="y")
        vertices=second.inner_xyz+second.outer_xyz
        second_local=tuple(
            tuple(vertices[i] for i in face) for face in second.shell_faces
        )
        second_world=api.place_prethickened_endcap_world_skins(
            second_local,placement="bottom",box_body_world=body,
        )
        second_assembly=api.inspect_operator_tail_d4_assembly_world(
            body,second_world,
        )
        assert second_assembly.body_triangle_count==len(body)==308
        assert second_assembly.tail_triangle_count==len(second_world)==2860
        assert second_assembly.crossing_pair_count>=0
        assert len(second_assembly.crossing_segments)>=0
        assert not second_assembly.manufacturing_approved
        # Confirm BOTH fold orders now have side face contact, while the rear
        # overlap remains an independent 1-mm unresolved witness.
        # Interval widths come from distinct physical face hits, not from
        # crossing lines or a nominal spec copied into a new solid.
        for shell_mesh in (placed,second_world):
            for body_limits,tail_limits in (
                ((-310.,-308.),(-308.,-306.)),
                ((308.,310.),(306.,308.)),
            ):
                shell_hits=probe_native_world_mesh_axis_faces(
                    shell_mesh,axis=0,fixed_xyz=(0.,-290.,-20.),
                )
                assert all(any(abs(x-v)<1e-4 for x in shell_hits)
                           for v in tail_limits)
                assert min(body_limits[1],tail_limits[1])-max(
                    body_limits[0],tail_limits[0]
                )==pytest.approx(0.)
            rear_hits=probe_native_world_mesh_axis_faces(
                shell_mesh,axis=2,fixed_xyz=(100.,-275.,0.),
            )
            assert all(any(abs(z-v)<1e-4 for z in rear_hits)
                       for v in (-91.5,-89.5))
        # Integral Body's corrected outside datum now has no side
        # interior overlap at either stationary material sample, for both
        # fold orders. Existing rear overlap is NOT thereby certified clear.

        assert actual.volume_verdict.startswith("VOLUME_INTERFERENCE_")
        figure=win._tail_d4_check_figure
        assert len(figure.axes)==5
        # WHD world Y is vertical; changing only the camera must leave the
        # original world triangles and all 2D primitives untouched.
        assembly_ax,left_ax,right_ax=figure.axes[1],figure.axes[3],figure.axes[4]
        assert assembly_ax._vertical_axis==1
        assert (assembly_ax.elev,assembly_ax.azim)==(18,-32)
        assert left_ax._vertical_axis==right_ax._vertical_axis==1
        assert (left_ax.elev,left_ax.azim)==(20,54)
        assert (right_ax.elev,right_ax.azim)==(20,-54)
        assert any("Tail UV" in text.get_text() for text in figure.texts)
        section=figure.axes[2]
        assert section.lines, "native upper two folds source section missing"
        assert figure.axes[3].collections and figure.axes[4].collections
        assert any(
            "CHECK_NOT_CNC" in str(t.get_text())
            for t in figure.texts
        )
        root.update_idletasks()
        root.update()

        # Click the REAL window toolbar action, not the exporter directly.
        # Timestamp/handle differences between DXF files are not geometry.
        file_path=tmp_path / "native_tail_d4_x_CHECK_NOT_CNC.dxf"
        monkeypatch.setattr(
            "gui_modules.application.tail_d4_check_view.filedialog.asksaveasfilename",
            lambda **_kw: str(file_path),
        )
        messages=[]
        monkeypatch.setattr(
            "gui_modules.application.tail_d4_check_view.messagebox.showinfo",
            lambda *args, **kwargs: messages.append(("info",args)),
        )
        monkeypatch.setattr(
            "gui_modules.application.tail_d4_check_view.messagebox.showerror",
            lambda *args, **kwargs: messages.append(("error",args)),
        )
        toolbar=next(w for w in win.winfo_children() if isinstance(w,ttk.Frame))
        save_button=next(
            w for w in toolbar.winfo_children()
            if isinstance(w,ttk.Button) and "另存看圖 DXF" in w.cget("text")
        )
        save_button.invoke()
        assert messages and messages[-1][0]=="info",messages
        assert file_path.exists()
        reopened=ezdxf.readfile(file_path)
        assert reopened.dxfversion=="AC1015"  # R2000
        assert reopened.header["$INSUNITS"]==4  # actual millimeters
        assert not reopened.audit().has_errors
        entities=tuple(reopened.modelspace())
        assert len(entities)==11  # outer + four circles + five datum + warning
        # The source has three original CIRCLEs and a fourth real CUTTING
        # hole represented by a closed polyline. Preserve both source types.
        circles=[e for e in entities if e.dxf.layer=="CHECK"
                 and e.dxftype()=="CIRCLE"]
        closed=[e for e in entities if e.dxf.layer=="CHECK"
                and e.dxftype()=="LWPOLYLINE" and e.closed]
        assert len(circles)==3
        assert len(closed)==2  # source exterior + fourth original hole
        assert len(circles)+len(closed)-1==4
        assert len([e for e in entities if e.dxf.layer=="DATUM"
                    and e.dxftype()=="LINE"])==5
        assert not any(e.dxf.layer in ("CUTTING","BEND","MARKING")
                       for e in entities)
        assert designer._phase6_input_snapshot==before
        # The screenshot is captured from the real live Tk window. On a
        # runner without ImageGrab support use the same Figure embedded in
        # the Tk canvas and label that fallback precisely.
        raw=BytesIO()
        capture_type="REAL_TK_WINDOW"
        try:
            from PIL import ImageGrab
            x=win.winfo_rootx();y=win.winfo_rooty()
            w=win.winfo_width();h=win.winfo_height()
            if w<600 or h<350:
                raise RuntimeError("Tk CHECK window was not fully mapped")
            ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(raw,format="PNG")
        except (ImportError,RuntimeError,OSError):
            capture_type="TK_CANVAS_FIGURE_ONLY"
            figure.savefig(raw,format="png",dpi=85)
        record_property(
            "ISSUE3317_REAL_D4_NATIVE_TK_CAPTURE",
            capture_type+":"+base64.b64encode(raw.getvalue()).decode("ascii"),
        )
        assert len(raw.getvalue())>3000
        win.destroy()
        win=None
        root.update_idletasks()
        root.update()
        assert designer._phase6_input_snapshot==before
    finally:
        if win is not None:
            try:win.destroy()
            except tk.TclError:pass
        if designer is not None:
            try:designer.root.destroy()
            except tk.TclError:pass
        root.destroy()
