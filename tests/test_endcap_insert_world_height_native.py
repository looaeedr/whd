"""Native Primary -> canonical Engine assembly: EndCap height occupation."""
from copy import deepcopy
import tkinter as tk

import pytest
from gui import BoxCalculatorGUI
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_corner_policy import (
    CornerTypeId, box_body_vertical_offsets, resolve_endcap_policy_assembly_semantics
)
from ae_engine.corner_type_ui import default_selection_for_box_assembly

def test_actual_factory_height_modes(monkeypatch, tmp_path):
    from ae_engine import assembly_collision

    calls = []
    original = assembly_collision.solve_world_backprojected_endcap_relief

    def observe_solver(**kwargs):
        calls.append((kwargs["endcap_part"], kwargs.get("endcap_offset", (0., 0., 0.))))
        return original(**kwargs)

    monkeypatch.setattr(assembly_collision, "solve_world_backprojected_endcap_relief", observe_solver)
    for head_type,tail_type in [('INSERT','INSERT'),('INSERT_OVERLAY','INSERT_OVERLAY'),
                                 ('OVERLAY','OVERLAY'),('INSERT','INSERT_OVERLAY'),
                                 ('INSERT_OVERLAY','INSERT')]:
        root=tk.Tk(); root.withdraw()
        try:
            host=BoxCalculatorGUI(root)
            host.baseline_var.set("自訂")
            for field,value in dict(w=400,h=600,d=250,t=2).items():
                getattr(host,f"{field}_var").set(str(value))
            host._set_box_assembly_type(CornerTypeId(head_type),recalculate=False,
                                       notify_designer=False,reset_bottom_defaults=True)
            # Isolated operator source fixture: retain each endpoint's real typed policy
            # rather than inventing a compensating offset. Asymmetry is diagnostic.
            for role,kind in (("head",head_type),("tail",tail_type)):
                for k in ("top_left","top_right"):
                    host.manual_corner_state[role][k]=default_selection_for_box_assembly(CornerTypeId(kind))
            calls.clear()
            designer=host.open_original_fold_designer()
            root.update()
            s=deepcopy(designer._phase6_input_snapshot)
            settings=dict(designer._settings_values)
            policies={k:api.resolve_operator_snapshot_corner_policy(
                k,corner_state=designer._phase6_corner_state,input_snapshot=s,settings_values=settings,
                endcap_fw_state=s.get("endcap_fw")) for k in ("head","tail")}
            semantics={k:resolve_endcap_policy_assembly_semantics(v).type_id.value for k,v in policies.items()}
            occupy=box_body_vertical_offsets(2,head_corner_policy=policies["head"],tail_corner_policy=policies["tail"])
            g=designer._phase6_resolve_manufacturing_geometry()
            coords=api.build_joint_world_geometry(g.parts,(400.,600.,250.),2.)["world_triangles_by_part"]
            def bounds(tris):
                ys=[v[1] for t in tris for v in t]
                return (min(ys),max(ys))
            def core(tris):
                planes=set()
                for t in tris:
                    if max(p[1] for p in t)-min(p[1] for p in t)<1e-8:
                        # Core is deliberately the central broad horizontal skin;
                        # the turned narrow flanges do not cross this XY footprint.
                        if min(p[0] for p in t)<=0<=max(p[0] for p in t) and min(p[2] for p in t)<=0<=max(p[2] for p in t):
                            planes.add(round(t[0][1],7))
                return sorted(planes)
            body=bounds(coords["box_body"])
            head,tail=core(coords["head"]),core(coords["tail"])
            assert len(head)>=2 and len(tail)>=2
            assert body[1] - body[0] == pytest.approx(600 - sum(occupy))
            assert (semantics["head"], semantics["tail"]) == (head_type, tail_type)
            head_face = body[1] + occupy[1]
            tail_face = body[0] - occupy[0]
            assert head == pytest.approx([head_face - 2, head_face])
            assert tail == pytest.approx([tail_face, tail_face + 2])
            overall=bounds(tuple(coords["box_body"])+tuple(coords["head"])+tuple(coords["tail"]))
            assert overall[1] - overall[0] == pytest.approx(600)
            if head_type == tail_type:
                assert overall == pytest.approx((-300, 300))
            print(head_type, tail_type, "body", body, "head", head, "tail", tail, "overall", overall)
            expected_offsets = {
                "head": (0., -2. if head_type == "INSERT" else 0., 0.),
                "tail": (0., 2. if tail_type == "INSERT" else 0., 0.),
            }
            assert {role: offset for role, offset in calls} == expected_offsets
            assert {part.part_key: part.offset for part in g.parts
                    if part.part_key in expected_offsets} == expected_offsets
            # Same canonical scene is rendered by another existing public
            # consumer. This is a thick assembled mesh, not the UV surface test.
            if head_type == tail_type == "INSERT":
                rows = api.resolve_receiving_settings_assembly_world_meshes(
                    g.parts, finished_dimensions=(400., 600., 250.), thickness=2.,
                    preserve_endcap_core_origin=True,
                )
                by_key = {key: mesh for _, key, mesh in rows}
                assert core(by_key["head"]) == pytest.approx(head)
                assert core(by_key["tail"]) == pytest.approx(tail)
                path = tmp_path / "pure-insert.p6fold"
                host._flush_phase6_authoritative_state()
                host.project_controller.save(path, host._compose_phase6_project_snapshot_from_main_gui)
                assert path.is_file()
                fresh_root = tk.Toplevel(root)
                fresh_root.withdraw()
                fresh = BoxCalculatorGUI(fresh_root)
                fresh.load_phase6_project(path, open_designer=False)
                again = fresh.open_original_fold_designer()._phase6_resolve_manufacturing_geometry()
                new = {part.part_key: part for part in again.parts}
                for part in g.parts:
                    if part.part_key in expected_offsets:
                        assert new[part.part_key].offset == part.offset
                        assert new[part.part_key].render_data.material.equals_exact(
                            part.render_data.material, 1e-8
                        )
                        assert tuple(new[part.part_key].render_data.fold_guides) == tuple(part.render_data.fold_guides)
        finally:
            root.destroy()
