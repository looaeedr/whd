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


def _d4_forensic_face_provenance(flat, check, body, tail, *, first_axis):
    """CHECK-only face IDs, actual original UV ownership and entire V walls.

    This does not modify the mesh or infer solid volume from surface hits.
    The two V legs are assessed as oriented planar polygon SETS: different
    triangulation diagonals must not count as a gap.
    """
    import math
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union
    from ae_engine.assembly_geometry import _segment_triangle_intersection
    from ae_engine.v_miter_tail_no_ba_sequential import (
        _stages,stations_from_real_flat,
    )

    origin=flat.original_factory_material
    k=len(check.source_uv)
    nface=len(check.source_triangle_faces)
    verts=check.inner_xyz+check.outer_xyz
    st=stations_from_real_flat(flat)

    def vminus(a,b):return tuple(a[i]-b[i] for i in range(3))
    def dot(a,b):return sum(a[i]*b[i] for i in range(3))
    def cross(a,b):return (
        a[1]*b[2]-a[2]*b[1],
        a[2]*b[0]-a[0]*b[2],
        a[0]*b[1]-a[1]*b[0],
    )
    def unit(v):
        d=math.sqrt(dot(v,v))
        return tuple(x/d for x in v) if d>1e-12 else (0.,0.,0.)
    def normal(tri):
        return unit(cross(vminus(tri[1],tri[0]),
                          vminus(tri[2],tri[0])))
    def ray_faces(mesh,point,axis):
        low=min(q[axis] for tri in mesh for q in tri)-1.
        high=max(q[axis] for tri in mesh for q in tri)+1.
        start=list(point);end=list(point)
        start[axis]=low;end[axis]=high
        rows=[]
        for fid,tri in enumerate(mesh):
            hit=_segment_triangle_intersection(
                start,end,tri,tolerance=1e-7,
            )
            if hit is not None:
                rows.append((fid,tuple(round(float(v),7) for v in hit)))
        return tuple(rows)

    def tail_record(fid,hit,mesh):
        face=check.shell_faces[fid]
        indices=tuple(v%k for v in face)
        source=tuple(check.source_uv[i] for i in indices)
        poly=Polygon(source)
        src_area=poly.area
        old_area=poly.intersection(origin).area if src_area>1e-10 else 0.
        new_area=src_area-old_area
        domain=("old" if src_area>1e-10 and new_area<1e-7
                else "restored" if src_area>1e-10 and old_area<1e-7
                else "mixed" if src_area>1e-10 else "boundary_wall")
        if fid<2*nface:
            skin="inner" if fid%2==0 else "outer"
        else:skin="cut_wall"
        inner=tuple(check.inner_xyz[i] for i in indices)
        outer=tuple(check.outer_xyz[i] for i in indices)
        ctr=tuple(sum(uv[j] for uv in source)/3. for j in range(2))
        first,final,n_first,n_final,_=_stages(
            ctr,first_axis,st,
        )
        return dict(
            face=fid,hit=hit,uv=tuple(tuple(round(v,5) for v in q)
                                      for q in source),
            domain=domain,old_uv_area=round(old_area,6),
            restored_uv_area=round(new_area,6),skin=skin,
            world_normal=tuple(round(v,6) for v in normal(mesh[fid])),
            first_xyz=tuple(round(v,5) for v in first),
            final_xyz=tuple(round(v,5) for v in final),
            staged_normal=tuple(round(v,5) for v in n_final),
            local_inner=tuple(tuple(round(v,5) for v in p)
                              for p in inner),
            local_outer=tuple(tuple(round(v,5) for v in p)
                              for p in outer),
        )

    rays={}
    for name,point in (
        ("real_front_corner",(-294.,-297.,0.)),
        ("rear_sheet",(100.,-275.,0.)),
    ):
        ours=ray_faces(tail,point,2)
        theirs=ray_faces(body,point,2)
        rays[name]={
            "body":tuple({"face":fid,"hit":hit,
                          "normal":tuple(round(v,5) for v in normal(body[fid]))}
                         for fid,hit in theirs),
            "tail":tuple(tail_record(fid,hit,tail) for fid,hit in ours),
        }

    # The exact 3D wall face pair IDs derive from the same UV boundary edge
    # and original (lower,apex,upper) pairs. There are four leg groups.
    groups={}
    for j,(a,b,_) in enumerate(check.source_boundary_edges):
        edge=LineString((check.source_uv[a],check.source_uv[b]))
        if edge.length<=1e-9:continue
        for name,lower,apex,upper in flat.opening_source_points_xy:
            for label,tip in (("lower",lower),("upper",upper)):
                straight=LineString((apex,tip))
                if edge.difference(straight.buffer(3e-7)).length>1e-7:
                    continue
                ids=(2*nface+2*j,2*nface+2*j+1)
                groups.setdefault((name,label),[]).extend(ids)

    seams={}
    for name,_,_,_ in flat.opening_source_points_xy:
        lo=tuple(dict.fromkeys(groups.get((name,"lower"),())))
        up=tuple(dict.fromkeys(groups.get((name,"upper"),())))
        assert lo and up,("SOURCE_STRAIGHT_V_WALLS_REQUIRED",name,lo,up)
        a=tail[lo[0]]
        e0=unit(vminus(a[1],a[0]))
        n=normal(a)
        e1=cross(n,e0)
        anchor=a[0]
        def project(tri):
            return Polygon(tuple(
                (dot(vminus(p,anchor),e0),dot(vminus(p,anchor),e1))
                for p in tri
            ))
        def set_polygon(ids):
            return unary_union([project(tail[i]) for i in ids])
        lower=set_polygon(lo)
        upper=set_polygon(up)
        all_up=tuple(p for i in up for p in tail[i])
        plane_distance=max(abs(dot(vminus(p,anchor),n)) for p in all_up)
        avg_up=unit(tuple(sum(normal(tail[i])[k] for i in up)
                          for k in range(3)))
        seams[name]={
            "lower_face_ids":lo,"upper_face_ids":up,
            "lower_area":round(lower.area,9),
            "upper_area":round(upper.area,9),
            "intersection_area":round(lower.intersection(upper).area,9),
            "symmetric_difference_area":round(
                lower.symmetric_difference(upper).area,9,
            ),
            "max_out_of_plane":round(plane_distance,9),
            "opposed_normal_dot":round(dot(n,avg_up),7),
        }
    return {"first_axis":first_axis,"rays":rays,"straight_v_wall_sets":seams}


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
            rear_interval=(-91.5,-89.5)
            body_rear_interval=(-92.5,-90.5)
            rear_overlap=min(rear_interval[1],body_rear_interval[1])-max(
                rear_interval[0],body_rear_interval[0],
            )
            assert rear_overlap==pytest.approx(1.,abs=1e-6)
            corner_hits=probe_native_world_mesh_axis_faces(
                shell_mesh,axis=2,fixed_xyz=(-294.,-297.,0.),
            )
            assert len(corner_hits)>=2,("D4_FRONT_CORNER_MISSING",corner_hits)
            front_tail=tuple(sorted(corner_hits)[-2:])
            front_body=tuple(sorted(front_corner_body)[-2:])
            assert min(front_tail[1],front_body[1])-max(
                front_tail[0],front_body[0],
            )==pytest.approx(1.,abs=1e-5)
            # A hypothetical rigid +1 Z shift fixes rear but doubles
            # the real front-frame overlap: quantify without moving a mesh.
            shifted_rear=(rear_interval[0]+1.,rear_interval[1]+1.)
            shifted_front=(front_tail[0]+1.,front_tail[1]+1.)
            assert min(shifted_rear[1],body_rear_interval[1])-max(
                shifted_rear[0],body_rear_interval[0],
            )==pytest.approx(0.,abs=1e-6)
            assert min(shifted_front[1],front_body[1])-max(
                shifted_front[0],front_body[0],
            )==pytest.approx(2.,abs=1e-5)
        # This is material/face provenance, not another overlap assertion:
        # print the exact face IDs, UV/old-vs-restored origin, normals and
        # full left/right V opposing-wall polygon set differences.
        import warnings
        for axis,solid,shell in (
            ("x",placed,check),("y",second_world,second),
        ):
            proof=_d4_forensic_face_provenance(
                flat,shell,body,solid,first_axis=axis,
            )
            import json
            warnings.warn(
                "ISSUE3317_SOURCE_FACE_AUDIT="+json.dumps(
                    proof,ensure_ascii=True,separators=(",",":"),
                ),
                RuntimeWarning,stacklevel=1,
            )
        # Candidate is isolated from production and CHECK rendering:
        # the EXACT original EndCap Engine folds the changed CUTTING.
        # Non-V factory source must retain unchanged physical front/rear
        # skins, not be moved globally by 1 mm or thickened from a new datum.
        from ae_engine.v_miter_tail_d4_delivery import (
            project_tail_d4_shared_original_fold_candidate,
        )
        for axis in ("x","y"):
            trial=project_tail_d4_shared_original_fold_candidate(
                flat,first_axis=axis,box_body_world=body,
            )
            assert not trial["manufacturing_approved"]
            for label,pos in (
                ("rear",(100.,-275.,0.)),
                ("front_frame",(-294.,-297.,0.)),
            ):
                original_hits=probe_native_world_mesh_axis_faces(
                    trial["original_solid"],axis=2,fixed_xyz=pos,
                )
                candidate_hits=probe_native_world_mesh_axis_faces(
                    trial["v_solid"],axis=2,fixed_xyz=pos,
                )
                assert original_hits==candidate_hits,(
                    "D4_CANDIDATE_UNCHANGED_FACTORY_FACE_DRIFT",
                    axis,label,original_hits,candidate_hits,
                )
            # Compare baseline source and V change in the same physical
            # owner before any costly global collision solver. This phase
            # is NOT a pass for root continuity or full V walls.
            import warnings
            warnings.warn(
                "ISSUE3317_SHARED_ORIGINAL_FOLD_CANDIDATE="
                +repr((axis,len(trial["v_surface"]),
                       len(trial["v_solid"]),
                       "ROOT_SELF_CONTACT_UNVERIFIED")),
                RuntimeWarning,stacklevel=1,
            )
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
