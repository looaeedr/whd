# -*- coding: utf-8 -*-
from types import SimpleNamespace

import pytest


def _snapshot(w=1200.0, t=2.0):
    return {
        "w": w, "h": 1600.0, "d": 400.0, "t": t, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
    }


def test_multi_piece_box_body_3d_draws_authoritative_bend_lines():
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from phase6_box_body_structure import (
        BoxBodyStructureType, default_box_body_structure_state, set_active_structure,
    )
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments
    from phase6_final_scene_view import Phase6FinalSceneView, FinalSceneViewRequest

    state = set_active_structure(
        default_box_body_structure_state(), BoxBodyStructureType.TWO_PIECE_W_SPLIT
    )
    spec = BoxBodyPartSpec(
        width=1200.0, height=1600.0, depth=400.0, thickness=2.0, frame_width=25.0,
        fold_profile=profile_to_fold_segments(build_box_body_profile(_snapshot())),
        structure_state=state,
    )
    data = build_box_body_structure_render_data(spec)

    class Axis:
        def __init__(self):
            self.collections = []
            self.lines = []
            self.plot_calls = []
            self.transAxes = object()
        def add_collection3d(self, obj): self.collections.append(obj)
        def plot(self, *args, **kwargs): self.plot_calls.append((args, kwargs)); return None
        def text2D(self, *args, **kwargs): return None
        def set_xlim3d(self, *args): pass
        def set_ylim3d(self, *args): pass
        def set_zlim3d(self, *args): pass
        def set_box_aspect(self, *args, **kwargs): pass

    axis = Axis()
    view = Phase6FinalSceneView(SimpleNamespace(ax3d=axis))
    view.render(FinalSceneViewRequest(
        render_data=data, x_profile=(), y_profile=(), part_key="box_body",
        alpha_bend=0.85, finished_dimensions=(1200.0, 1600.0, 400.0), thickness=2.0,
    ))

    bend_count = sum(
        1 for piece in data.pieces for p in piece.render_data.scene.primitives
        if str(getattr(p, "layer", "")).upper() == "BEND"
    )
    assert bend_count > 0
    assert len(axis.plot_calls) >= bend_count, "每一條 manufacturing BEND 都必須在結構箱身 3D 可見"


def test_structure_switch_materializes_type_defaults_into_canonical_state():
    from phase6_box_body_structure import (
        BoxBodyStructureType, default_box_body_structure_state,
        activate_structure_with_defaults,
    )

    state = default_box_body_structure_state()
    two = activate_structure_with_defaults(state, BoxBodyStructureType.TWO_PIECE_W_SPLIT, total_w=800.0)
    cfg2 = two["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
    assert (cfg2["left_w"], cfg2["right_w"]) == pytest.approx((400.0, 400.0))

    three = activate_structure_with_defaults(two, BoxBodyStructureType.THREE_PIECE_W_SPLIT, total_w=800.0)
    cfg3 = three["configs"][BoxBodyStructureType.THREE_PIECE_W_SPLIT.value]
    assert (cfg3["left_w"], cfg3["middle_w"], cfg3["right_w"]) == pytest.approx((50.0, 700.0, 50.0))


def test_receiving_phase6_policy_keeps_family_specific_bottom_effective_fw():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        designer.activate_part("head")
        root.update_idletasks(); root.update()
        policy = bridge._phase6_corner_policy_for(designer, "head")
        assert policy.bottom_fw == pytest.approx(17.0), "側板後折15 + 1T(2) 應成為受電箱下方等價 FW"
        assert policy.fw == pytest.approx(29.0)
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_relief_registry_form_is_traditional_chinese_and_explains_internal_terms():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw()
    app = SimpleNamespace(root=root)
    win = None
    try:
        # Minimal host state needed by the form refresh routines.
        from phase6_designer_workspace import Phase6DesignerWorkspace
        app.designer_workspace = Phase6DesignerWorkspace.from_snapshot({"existing_parts": ["box_body", "head", "tail"]})
        app._phase6_input_snapshot = {}
        win = bridge._phase6_open_relief_registry_form(app)
        root.update_idletasks(); root.update()

        assert "組合接合" in win.title()
        texts = []
        def walk(w):
            for child in w.winfo_children():
                if "text" in child.keys():
                    texts.append(str(child.cget("text")))
                walk(child)
        walk(win)
        joined = "\n".join(texts)
        for english in ("Rule ID", "Assembly Intent", "Target Role", "Subject Region", "Relation", "Clearance"):
            assert english not in joined
        for chinese in ("規則名稱", "組合方式", "主要接合對象", "公式變數說明", "板厚", "成型接合寬"):
            assert chinese in joined
    finally:
        if win is not None:
            try: win.destroy()
            except Exception: pass
        root.destroy()


def test_real_structure_selector_commits_defaults_and_changes_3d_piece_topology():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    from phase6_box_body_structure import BoxBodyStructureType

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        designer = app.open_original_fold_designer()
        designer.activate_part("box_body")
        root.update_idletasks(); root.update()
        w = bridge._phase6_box_structure_w(designer)

        designer.structure_type_var.set("二件式（W 二分）")
        bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
        root.update_idletasks(); root.update()
        state = bridge._phase6_box_structure_state(designer)
        cfg = state["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
        assert (cfg["left_w"], cfg["right_w"]) == pytest.approx((w / 2.0, w / 2.0))
        data = bridge._phase6_query_final_render_data(designer)
        assert [p.role for p in data.pieces] == ["left", "right"]

        designer.structure_type_var.set("三件式（W 三分）")
        bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
        root.update_idletasks(); root.update()
        state = bridge._phase6_box_structure_state(designer)
        cfg = state["configs"][BoxBodyStructureType.THREE_PIECE_W_SPLIT.value]
        assert (cfg["left_w"], cfg["middle_w"], cfg["right_w"]) == pytest.approx((50.0, w - 100.0, 50.0))
        data = bridge._phase6_query_final_render_data(designer)
        assert [p.role for p in data.pieces] == ["left", "middle", "right"]
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_receiving_structure_selector_is_family_locked_by_model_source_of_truth():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    from phase6_box_body_structure import BoxBodyStructureType

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        assert str(designer.structure_choice_button.cget("state")) == "disabled"
        assert designer.designer_workspace.box_body_structure_state()["active_type"] == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_receiving_wrap_intent_callback_preserves_bottom_relief_before_and_after_3d_solver():
    """受電箱只有明確選擇包覆貼外時，BOTTOM WRAP relief 才能穿過 adapter 並在 3D solve 後保留。"""
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge
    from ae_engine import manufacturing_api
    from ae_engine.assembly_collision import measure_material_corner_reliefs
    from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        # Receiving family 本身只提供幾何；正式「包覆貼外」preset 才擁有 BOTTOM WRAP。
        designer.assembly_type_var.set("包覆貼外")
        bridge._phase6_on_assembly_type_selected(designer)
        root.update_idletasks(); root.update()
        for part_key in ("head", "tail"):
            assert edge_relation_for_part(
                designer._phase6_input_snapshot, part_key, "BOTTOM"
            ) is AssemblyJointRelation.WRAP

        def measurements(render_data):
            material = manufacturing_api.material_polygon_from_final_scene(render_data.scene)
            return {m.corner_name: m for m in measure_material_corner_reliefs(material, blank_bounds=material.bounds)}

        # Payload adapter 可保留 display bottom_fw=17；真正 machining CUT 由
        # 已解析為 WRAP 的 BOTTOM Joint 命中 Certified Registry。
        for part_key in ("head", "tail"):
            payload = bridge._phase6_scene_query_payload_for_part(designer, part_key)
            payload["_use_committed_relief"] = False
            spec, _ctx = app._fold_designer_part_spec_from_payload(part_key, payload)
            assert spec.corner_policy.bottom_fw == pytest.approx(17.0)

            raw = designer._scene_query_callback(part_key, payload)
            raw_m = measurements(raw)
            physical_bottom = "top_left" if part_key == "head" else "bottom_left"
            assert raw_m[physical_bottom].primary_u == pytest.approx(28.0)
            assert raw_m[physical_bottom].primary_v == pytest.approx(14.0)
            assert raw_m[physical_bottom].secondary_u == pytest.approx(15.0)
            assert raw_m[physical_bottom].secondary_depth == pytest.approx(1.0)

        # Full 3D solve 可更新 TOP assembly corners，但已明確選定的 BOTTOM WRAP
        # manufacturing corner 必須保留，不能被上方 solve 覆蓋。
        resolved = bridge._phase6_resolve_manufacturing_geometry(designer)
        assembly_bundle = bridge._phase6_query_assembly_render_data(designer)
        assert assembly_bundle.preserve_endcap_core_origin is True
        assert dict(getattr(designer, "_phase6_last_relief_errors", {}) or {}) == {}
        solutions = dict(getattr(designer, "_phase6_last_relief_solutions", {}) or {})
        for part_key in ("head", "tail"):
            final = resolved.part(part_key)
            final_m = measurements(final.render_data)
            physical_bottom = "top_left" if part_key == "head" else "bottom_left"
            assert final_m[physical_bottom].primary_u == pytest.approx(28.0)
            assert final_m[physical_bottom].primary_v == pytest.approx(14.0)
            assert final_m[physical_bottom].secondary_u == pytest.approx(15.0)
            assert final_m[physical_bottom].secondary_depth == pytest.approx(1.0)
            solution = solutions[part_key]
            assert solution.verified is True
            assert solution.residual_projection is not None
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
