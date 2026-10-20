"""#1959 original WHD main toolbar Save/Open with CADCraft-approved hole Features.

The native CADCraft process and its geometry transfer are covered by the
sibling Windows GUI test. This test exercises the separate REAL main toolbar
buttons and canonical .p6fold→DoorPartSpec manufacturing, no fake save/load.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import os

import ezdxf
import pytest

from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.manufacturing_api import generate_part
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from phase6_project_file import read_project
from tools.issue1959_whd_real_manufacturing_parity import _features, _signature


def _door_export(features, output, root):
    context = ManufacturingContext(resource_root=root, draw_stock=False)
    generate_part(DoorPartSpec(
        width=500, height=600, thickness=2, frame_width=25,
        gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=19, fold_top=19, fold_bottom=19,
        features=tuple(features),
    ), output, context)
    return Counter(_signature(entity) for entity in
                   ezdxf.readfile(output).modelspace())


def test_cadcraft_approved_features_survive_actual_whd_main_toolbar_save_open(
    tmp_path, monkeypatch,
):
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        pytest.skip("requires actual Tk display")
    import tkinter as tk
    import tkinter.filedialog as filedialog
    import gui

    root = tk.Tk()
    root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("金庫型")
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("350")
        app._apply_existing_parts_from_fold_workspace(["box_body", "door"])
        root.update_idletasks()
        root.update()

        old, additions = _features()  # The same native CADCraft parity cases.
        owned = app.surface_features.setdefault("door", [])
        owned[:] = [old]
        identity = id(owned)
        # Existing WHD Session, not a parallel CADCraft persistence store.
        session = Phase6HoleEditorSession("door", owned)
        session.execute(HoleEditorAction.preview_all((old, *additions)))
        assert session.has_active_edit
        session.execute(HoleEditorAction.commit_active())
        session.finish(commit=True)
        accepted = tuple(owned)
        assert id(owned) == identity and len(accepted) == 4

        authority_root = tmp_path / "authority"
        authority_root.mkdir()
        before = _door_export(
            accepted, tmp_path / "before-toolbar-reload.dxf", authority_root
        )

        # Actually INVOKE WHD's global 'Save As' toolbar button. Only dialog
        # file selection is injected, never project.save or read_project.
        project_path = tmp_path / "WHD-CADCraft-confirmed.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename",
                            lambda **kw: str(project_path))
        app.project_save_as_button.invoke()
        assert project_path.is_file(), "WHD_MAIN_TOOLBAR_SAVE_AS_DID_NOT_WRITE"
        persisted = read_project(project_path)
        saved = tuple(persisted["snapshot"]["part_features"]["door"])
        assert saved == accepted, "CADCRAFT_CONFIRMED_FEATURES_MISSING_FROM_GUI_SAVE"
        assert not persisted["final_geometry"]
        assert "door" in persisted["snapshot"]["existing_parts"]

        # Destroy the live working Feature contents before opening. An actual
        # main-toolbar Open must reconstruct them from the .p6fold on disk.
        owned[:] = [old]
        assert tuple(owned) != accepted
        monkeypatch.setattr(filedialog, "askopenfilename",
                            lambda **kw: str(project_path))
        app.project_open_button.invoke()
        root.update_idletasks()
        root.update()

        restored = tuple(app.surface_features.get("door", ()))
        assert restored == accepted, "WHD_MAIN_TOOLBAR_OPEN_LOST_APPROVED_CADCraft_HOLES"
        assert len(restored) == 4
        assert app.project_controller.project_path == str(project_path)
        assert "door" in app._phase6_existing_parts

        # Verify that the WHD true Save button subsequently preserves the
        # restored holes, without asking for a second project filename.
        monkeypatch.setattr(filedialog, "asksaveasfilename",
                            lambda **kw: (_ for _ in ()).throw(
                                AssertionError("Save should reuse project path")
                            ))
        app.project_save_button.invoke()
        re_saved = tuple(read_project(project_path)["snapshot"]["part_features"]["door"])
        assert re_saved == accepted, "WHD_MAIN_TOOLBAR_SAVE_LOST_RESTORED_CADCraft_HOLES"

        # WHD alone regenerates complete manufacturing geometry from the
        # restored main-app Features; CADCraft DXF is not an input here.
        after = _door_export(
            re_saved, tmp_path / "after-toolbar-reload.dxf", authority_root
        )
        assert before == after, "WHD_GUI_RELOAD_MANUFACTURING_GEOMETRY_DRIFT"
        assert any(layer == "CUTTING" and kind == "CIRCLE"
                   for kind, layer, _ in after)

        # The saved main-GUI Feature collection must also reach the actual
        # Fold Designer source and the same physical assembly material. A DXF
        # or .p6fold-only PASS does not prove the 2D/3D part was updated.
        import fold_designer_bridge as bridge
        from ae_engine.sheetmetal_drawing import CirclePrimitive
        from phase6_manufacturing_adapter import build_scene_payload_for_app

        designer = app.open_original_fold_designer()
        root.update_idletasks()
        root.update()
        assert "door" in designer.available_parts
        designer.activate_part("door")
        root.update_idletasks()
        root.update()
        observed = tuple(designer.designer_workspace.features_for("door"))
        assert observed == accepted, "RELOADED_DOOR_FEATURES_MISSING_FROM_3D_WORKSPACE"
        payload = build_scene_payload_for_app(designer, "door")
        assert tuple(payload["features"]) == accepted, "DOOR_2D3D_SOURCE_MISMATCH"
        render = designer._scene_query_callback("door", payload)
        assert render is not None and render.material.area > 0
        cutting_circles = tuple(
            p for p in render.scene.primitives
            if isinstance(p, CirclePrimitive) and p.layer == "CUTTING"
        )
        assert len(cutting_circles) >= 2, "DOOR_CADCraft_CIRCLES_NOT_IN_2D_SCENE"

        assembled = bridge._phase6_final_scene_adapter(
            designer
        ).query_assembly_render_data()
        physical = {p.part_key: p for p in assembled.assembly_parts}
        assert "door" in physical, "RELOADED_DOOR_ABSENT_FROM_REAL_3D_ASSEMBLY"
        physical_door = physical["door"].render_data
        assert physical_door.material.area > 0
        assert abs(physical_door.material.area - render.material.area) < 1e-5, (
            "DOOR_REAL_2D_3D_PHYSICAL_MATERIAL_DISAGREES"
        )

        # #1959 VISUAL RED oracle: real Matplotlib FinalScene pixels, not a
        # sketch, fabricated screenshot, or a triangle/metadata count.
        # Compare exactly the same committed material and camera while
        # toggling ONLY the existing cyan CUTTING rim overlay.
        import json
        import numpy as np

        material = render.material
        polygons = (
            (material,) if material.geom_type == "Polygon"
            else tuple(getattr(material, "geoms", ()))
        )
        inner_rings = sum(len(p.interiors) for p in polygons
                          if getattr(p, "geom_type", "") == "Polygon")
        assert inner_rings >= 4, "RELOADED_CADCRAFT_REAL_3D_MATERIAL_HAS_MISSING_HOLES"

        designer._phase6_3d_display_mode = "single"
        view = designer.final_scene_view
        request = bridge._phase6_final_scene_adapter(designer).build_request()
        assert request is not None and request.part_key == "door"
        assert request.render_data.material.equals(material)
        ax = view.renderer.ax3d
        canvas = view.renderer.canvas
        real_rim_drawing = view._draw_cutting_hole_rims
        rim_segments = []

        def traced_real_rims(*args, **kwargs):
            n = real_rim_drawing(*args, **kwargs)
            rim_segments.append(n)
            return n

        def native_canvas_pixels(*, rims):
            ax.clear()
            view._draw_cutting_hole_rims = (
                traced_real_rims if rims else lambda *a, **kw: 0
            )
            try:
                triangles = view.render(request)
                assert triangles and view.last_cutting_material.equals(material)
                ax.view_init(elev=82, azim=-90)
                canvas.draw()
                return np.asarray(canvas.buffer_rgba()).copy()
            finally:
                view._draw_cutting_hole_rims = real_rim_drawing

        without_rims = native_canvas_pixels(rims=False)
        with_rims = native_canvas_pixels(rims=True)
        assert with_rims.shape == without_rims.shape
        assert len(rim_segments) == 1 and rim_segments[0] >= 30, (
            "RELOADED_CADCRAFT_3D_CUTTING_RIMS_NOT_DRAWN"
        )
        delta = np.max(np.abs(
            with_rims[:, :, :3].astype(np.int16)
            - without_rims[:, :, :3].astype(np.int16)
        ), axis=2)
        changed_pixels = int(np.count_nonzero(delta > 40))
        cyan_visible = int(np.count_nonzero(
            (delta > 40)
            & (with_rims[:, :, 0] < 130)
            & (with_rims[:, :, 1] > 145)
            & (with_rims[:, :, 2] > 155)
        ))
        print(
            "WHD_NATIVE_CADCRAFT_3D_HOLE_PIXELS "
            f"rings={inner_rings} rim_segments={rim_segments[0]} "
            f"changed_pixels={changed_pixels} cyan_visible={cyan_visible}",
            flush=True,
        )
        evidence_dir = os.environ.get("WHD_1959_PIXEL_RECEIPT_DIR")
        if evidence_dir:
            from PIL import Image
            output = Path(evidence_dir)
            output.mkdir(parents=True, exist_ok=True)
            Image.fromarray(without_rims).save(output / "real-door-rims-hidden.png")
            Image.fromarray(with_rims).save(output / "real-door-rims-visible.png")
            Image.fromarray(np.clip(delta * 4, 0, 255).astype("uint8")).save(
                output / "real-door-rims-pixel-difference.png"
            )
            (output / "real-door-rims-receipt.json").write_text(
                json.dumps({
                    "source": "original WHD FinalScene renderer; GUI .p6fold reload",
                    "canvas_shape": list(with_rims.shape),
                    "material_hole_rings": inner_rings,
                    "rim_segments": rim_segments[0],
                    "changed_pixels": changed_pixels,
                    "cyan_visible_pixels": cyan_visible,
                    "camera_elev": 82,
                    "camera_azim": -90,
                    "comparison": "identical true physical mesh; CUTTING rim overlay only",
                    "windows_user_uat": False,
                }, indent=2) + "\n", encoding="utf-8"
            )
        assert changed_pixels >= 130 and cyan_visible >= 60, (
            "RELOADED_CADCRAFT_3D_HOLE_RIMS_NOT_VISIBLE_IN_REAL_PIXELS"
        )
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
