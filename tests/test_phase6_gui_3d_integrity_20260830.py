from __future__ import annotations

from types import SimpleNamespace
import os

import pytest

import fold_designer_bridge as bridge


def test_unfolded_blank_operator_text_has_piece_sizes_without_area_or_raw_ids():
    from shapely.geometry import box
    from ae_engine.manufacturing_api import BoxBodyStructureRenderData, BoxBodyPieceRenderData, PartRenderData

    left = PartRenderData(scene=object(), material=box(0, 0, 123, 456))
    right = PartRenderData(scene=object(), material=box(0, 0, 234, 456))
    render = BoxBodyStructureRenderData(
        structure_type="two_piece_w_split",
        pieces=(
            BoxBodyPieceRenderData(key="left", role="left", formed_w_start=0, formed_w_end=100, fold_profile=(), render_data=left),
            BoxBodyPieceRenderData(key="right", role="right", formed_w_start=100, formed_w_end=200, fold_profile=(), render_data=right),
        ),
        preview_render_data=left,
    )
    text = bridge._phase6_format_unfolded_blank_text(render, part_key="box_body")
    assert "左箱身 123 × 456 mm" in text
    assert "右箱身 234 × 456 mm" in text
    assert "淨面積" not in text
    assert "mm²" not in text
    assert "left" not in text.lower()
    assert "right" not in text.lower()


def test_operator_label_maps_registry_and_joint_tokens_to_traditional_chinese():
    expected = {
        "INSERT": "嵌入",
        "OVERLAY": "貼外",
        "INSERT_OVERLAY": "嵌入貼外",
        "WRAP": "外側包覆",
        "HEAD_OR_TAIL": "封頭／封尾",
        "TOP": "上方",
        "BOTTOM": "下方",
        "USER_ADDED": "使用者新增",
        "ENDCAP_TOP_OVERLAY_STANDARD_V1": "封頭尾上方貼外（標準）",
        "RECEIVING_ENDCAP_BOTTOM_WRAP_V1": "受電箱封頭尾下方外側包覆",
    }
    for raw, label in expected.items():
        assert bridge._phase6_operator_label(raw) == label


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_dynamic_switch_to_receiving_updates_visible_structure_and_family_state():
    import tkinter as tk
    import gui
    from phase6_box_body_structure import BoxBodyStructureType

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        assert designer.structure_type_var.get() == "一體成型"

        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()

        assert designer.structure_type_var.get() == "三件式（側背分離）"
        assert designer.designer_workspace.box_body_structure_state()["active_type"] == (
            BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
        )
        assert str(designer.structure_choice_button.cget("state")) == "disabled"
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_overlay_live_rebuild_replaces_active_endcap_x_profile_and_workspace_together():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        designer = app.open_original_fold_designer()
        designer.activate_part("head")
        root.update_idletasks(); root.update()
        assert designer.state.profiles["X"]

        designer.assembly_type_var.set("貼外")
        bridge._phase6_on_assembly_type_selected(designer)
        root.update_idletasks(); root.update()

        active_x = list(designer.state.profiles["X"])
        stored_x = list(designer.designer_workspace.profiles_for("head")["X"])
        assert len(active_x) == 1
        assert len(stored_x) == 1
        assert active_x[0].get("phase6_key") == "endcap_w_flat"
        assert stored_x[0].get("phase6_key") == "endcap_w_flat"
        assert designer.state.phase6_fold_ui_tabs == ["Y"]
        assert list(getattr(designer.bend_ui, "tabs", ())) == ["Y"]
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_assembly_parts_panel_is_scrollable_and_wheel_bound_inside_rows():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        assert designer.assembly_parts_canvas.winfo_exists()
        assert designer.assembly_parts_scrollbar.winfo_exists()
        assert designer.assembly_parts_content.winfo_exists()
        assert designer.assembly_parts_canvas.cget("yscrollcommand")
        assert designer.assembly_parts_scrollbar.cget("command")

        widgets = [designer.assembly_parts_content]
        widgets.extend(designer.assembly_parts_content.winfo_children())
        assert any(w.bind("<MouseWheel>") for w in widgets)
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_shared_2d_viewport_reserves_annotation_and_dimension_lanes():
    import gui
    transform, left, bottom, scale, top = gui._phase6_2d_material_viewport(
        (0, 0, 800, 600), 1000, 760
    )
    assert scale > 0
    assert top >= 175.0
    assert left >= 48.0
    assert left + 800 * scale <= 1000 - 82.0 + 1e-6
    assert bottom <= 760 - 48.0 + 1e-6
    # Transform must place world material wholly below the annotation band.
    _x0, y0 = transform.world_to_canvas(gui.Vec2(0, 0))
    _x1, y1 = transform.world_to_canvas(gui.Vec2(800, 600))
    assert min(y0, y1) >= 175.0 - 1e-6


def test_final_scene_request_renders_canonical_unfolded_text_on_single_and_assembly_3d():
    from types import SimpleNamespace
    from shapely.geometry import box
    from ae_engine.sheetmetal_drawing import DrawingScene
    import phase6_final_scene_view as view

    class Axis:
        def __init__(self):
            self.collections = []
            self.lines = []
            self.text2d = []
            self.transAxes = object()
        def add_collection3d(self, obj): self.collections.append(obj)
        def plot(self, *args, **kwargs): return None
        def text(self, *args, **kwargs): return None
        def text2D(self, *args, **kwargs):
            self.text2d.append(str(args[2]))
            return None
        def set_xlim3d(self, *args): return None
        def set_ylim3d(self, *args): return None
        def set_zlim3d(self, *args): return None
        def set_box_aspect(self, *args, **kwargs): return None

    material = box(0, 0, 100, 60)
    part = SimpleNamespace(scene=DrawingScene(), material=material, fold_guides=())
    renderer = SimpleNamespace(ax3d=Axis())
    scene_view = view.Phase6FinalSceneView(renderer)
    flat_x = ({"len": 100.0, "core": True},)
    flat_y = ({"len": 60.0, "core": True},)
    scene_view.render(view.FinalSceneViewRequest(
        render_data=part,
        x_profile=flat_x,
        y_profile=flat_y,
        part_key="door",
        finished_dimensions=(100.0, 60.0),
        unfolded_blank_text="展開料：100 × 60 mm",
    ))
    assert any("展開料：100 × 60 mm" in text for text in renderer.ax3d.text2d)

    renderer.ax3d.text2d.clear()
    assembly = view.AssemblySceneRenderData(
        assembly_parts=(view.AssemblyScenePart(
            part_key="door", render_data=part,
            x_profile=flat_x, y_profile=flat_y, placement="front",
        ),),
    )
    scene_view.render(view.FinalSceneViewRequest(
        render_data=assembly,
        x_profile=(), y_profile=(), part_key="assembly",
        finished_dimensions=(100.0, 60.0, 20.0),
        unfolded_blank_text="展開尺寸：\n門：100 × 60 mm",
    ))
    assert any("展開尺寸：" in text and "門：100 × 60 mm" in text for text in renderer.ax3d.text2d)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_registry_operator_form_hides_stable_english_rule_ids():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        designer = app.open_original_fold_designer()
        win = bridge._phase6_open_relief_registry_form(designer)
        root.update_idletasks(); root.update()
        tree = designer.relief_registry_rule_tree
        assert tree.heading("id")["text"] == "規則名稱"
        selected = next((iid for iid in tree.get_children() if str(iid).startswith("ENDCAP_")), None)
        assert selected is not None
        tree.selection_set(selected)
        bridge._phase6_registry_rule_selected(designer)
        assert "ENDCAP_" not in designer.relief_registry_rule_name_var.get()
        assert designer.relief_registry_rule_id_var.get().startswith("ENDCAP_")  # internal only
        visible_labels = []
        visible_entries = []
        def walk(widget):
            for child in widget.winfo_children():
                try:
                    if child.winfo_class() in {"TLabel", "Label", "TLabelframe", "Labelframe"}:
                        visible_labels.append(str(child.cget("text")))
                    if child.winfo_class() in {"TEntry", "Entry"}:
                        visible_entries.append(str(child.get()))
                except Exception:
                    pass
                walk(child)
        walk(win)
        assert "規則代號" not in visible_labels
        visible_text = "\n".join(visible_labels + visible_entries)
        for raw_token in ("ENDCAP_", "INSERT", "OVERLAY", "side_fold", "ytop1", "mating_width", "x_folded", "x_flat", "USER_ADDED", "WRAP"):
            assert raw_token not in visible_text
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_real_box_body_2d_annotations_do_not_overlap_each_other_or_material():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.geometry("1400x900")
    app = gui.BoxCalculatorGUI(root)
    try:
        root.update_idletasks(); root.update()
        app.update_calculations(); root.update_idletasks(); root.update()
        canvas = app.canvas_z
        overview = app.last_box_body_face_overview
        transform = overview["transform"]
        _zw, zh = overview["unfolded_size"]
        material_top = min(
            transform.world_to_canvas(gui.Vec2(0, 0))[1],
            transform.world_to_canvas(gui.Vec2(0, zh))[1],
        )
        boxes = []
        for tag in ("phase6_preview_hint", "phase6_corner_dimensions", "phase6_hole_hint"):
            ids = canvas.find_withtag(tag)
            assert ids, tag
            bbox = canvas.bbox(ids[0])
            assert bbox is not None
            assert bbox[3] <= material_top
            boxes.append(bbox)
        def overlaps(a, b):
            return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                assert not overlaps(a, b), (a, b)
    finally:
        root.destroy()
