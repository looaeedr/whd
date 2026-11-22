# -*- coding: utf-8 -*-
"""#3317 native WHD main GUI: existing non-V CUTTING survives V -> save/open -> original.

No mocked Engine, resolver, viewport, project reader/writer or selector:
only Tk file-chooser destinations are supplied for unattended GitHub Xvfb.
This is a GUI preview/persistence regression, not CNC authorization.
"""
from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import pytest
from shapely.geometry import Polygon

import gui
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_feature_core import RectFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_hole_editor_session import Phase6HoleEditorSession, HoleEditorAction
from phase6_project_file import read_project


def _material_holes(render):
    assert render.material.geom_type == "Polygon"
    return tuple(Polygon(ring) for ring in render.material.interiors)


def _real_tail_selector(designer):
    designer.activate_part("tail")
    page = designer.settings_panel.render_context("tail")
    extension = page["extension_state"]
    chooser = extension["tail_lower_v_choice_widget"]
    var = extension["tail_lower_v_choice_var"]
    assert chooser is not None and var is not None
    assert chooser.winfo_exists()
    return chooser, var


def _real_resolved_tail(designer):
    geometry = designer._phase6_resolve_manufacturing_geometry()
    tail = geometry.part("tail")
    assert tail is not None and tail.render_data is not None
    return tail.render_data


def _assert_same_holes(before, after):
    originals = _material_holes(before)
    updates = _material_holes(after)
    assert len(originals) >= 1
    # The original Factory square can sit inside the old cutaway corner,
    # then become a real through-hole when the selected V restores that stock.
    # Existing operator holes must survive; new legitimate fixed holes may
    # appear, but losing an old hole is never allowed.
    assert len(updates) >= len(originals)
    assert all(any(a.symmetric_difference(b).area < 1e-5 for b in updates)
               for a in originals)
    return originals


@pytest.mark.parametrize("operator_first_axis",(None,"x","y"))
def test_actual_whd_main_gui_lower_v_preserves_existing_rect_clearance_roundtrip(
    tmp_path, monkeypatch, operator_first_axis,
):
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        pytest.skip("native WHD GUI requires a real Tk/Xvfb display")
    root = tk.Tk()
    root.withdraw()
    destination = tmp_path / "vault-tail-620x185-existing-clearance.p6fold"
    try:
        def fail_dialog(title, description, **_kwargs):
            raise AssertionError(f"unexpected native GUI error {title}: {description}")

        monkeypatch.setattr(messagebox, "showerror", fail_dialog)
        monkeypatch.setattr(filedialog, "asksaveasfilename",
                            lambda **_kw: str(destination))
        monkeypatch.setattr(filedialog, "askopenfilename",
                            lambda **_kw: str(destination))
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set("金庫型")
        main.w_var.set("620")
        main.h_var.set("600")
        main.d_var.set("185")
        if hasattr(main, "t_var"):
            main.t_var.set("2")
        main._apply_existing_parts_from_fold_workspace(
            ["box_body", "head", "tail"],
        )

        # Commit a genuine operator CUTTING cutout through the existing
        # WHD HoleEditor transaction, before choosing the V. This is an
        # independent rectangular clearance, not a fixture seam or V leg.
        feature = RectFeature(
            8.0, 10.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            Vec2(200.0, 115.0),
        )
        owned = main.surface_features.setdefault("tail", [])
        baseline_features = tuple(owned)
        session = Phase6HoleEditorSession("tail", owned)
        session.execute(HoleEditorAction.preview_all((*baseline_features, feature)))
        session.execute(HoleEditorAction.commit_active())
        session.finish(commit=True)
        assert feature in owned

        designer = main.open_original_fold_designer()
        root.update_idletasks()
        root.update()
        # The WHD fresh-start Tail has a 15-mm material lower fold, whereas
        # this operator's actual lower V scenario has a 48-mm material fold.
        # Edit the REAL Tk Fold Editor row (formed/outside display), using
        # Engine's own display projection for the corresponding material.
        # A generic Settings-only ybottom1 update would leave the existing
        # physical Y Fold Profile at 15 mm and create a false source mismatch.
        designer.activate_part("tail")
        editor = designer.bend_ui
        editor.nb.select(editor.tabs.index("Y"))
        root.update_idletasks()
        root.update()
        # Use the native tab-changed/render path so the controls belong to
        # the Tail Y profile rather than the previous page's X/head rows.
        editor.on_tab(None)
        editor.render()
        assert editor.state.active_bend == "Y"
        rows = editor.get_active_dict()["Y"]
        bottom_idx = next(i for i, seg in enumerate(rows)
                          if seg.get("phase6_key") == "ybottom1")
        candidate_rows = [dict(seg) for seg in rows]
        candidate_rows[bottom_idx]["len"] = 48.0
        displayed = api.project_operator_fold_editor_display_rows(
            candidate_rows, getattr(designer.state, "phase6_thickness", 2.0),
        )
        editor.controls[bottom_idx]["len"].set(
            str(displayed[bottom_idx]["len"])
        )
        editor.save()
        saved_y = editor.get_active_dict()["Y"]
        assert saved_y[bottom_idx]["len"] == pytest.approx(48.0)
        assert next(seg["len"] for seg in saved_y
                    if seg.get("phase6_key") == "ytop1") == pytest.approx(16.0)
        designer._save_current_part(notify=False)
        root.update_idletasks()
        root.update()
        chooser, selected = _real_tail_selector(designer)
        assert selected.get() == "原樣"
        # Physical spec and CUTTING must BOTH reflect this operator edit.
        from phase6_manufacturing_adapter import build_scene_payload_for_app
        from ae_engine.manufacturing_render_data import material_polygon_from_final_scene
        source_payload = dict(build_scene_payload_for_app(designer, "tail"))
        source_payload["_use_committed_relief"] = False
        live_spec, _ = designer._part_spec_query_callback("tail", source_payload)
        assert live_spec.fold_bottom == pytest.approx(48.)
        assert live_spec.fold_top == pytest.approx(16.)
        live_raw = designer._scene_query_callback("tail", source_payload)
        assert live_raw.material.bounds[3] == pytest.approx(268.)
        assert live_raw.material.symmetric_difference(
            material_polygon_from_final_scene(live_raw.scene)
        ).area < 1e-6
        original = _real_resolved_tail(designer)
        original_holes = _material_holes(original)
        assert len(original_holes) >= 1
        source_lines = api.project_operator_tail_lower_v_first_bend_options(
            live_spec, live_raw,
        )
        original_page = designer.settings_panel.render_context("tail")
        original_controls = original_page["extension_state"]
        for corner, x in (("bottom_left", 15.), ("bottom_right", 627.)):
            row = source_lines[corner]["x"]
            assert row["bend"] == [[x, 49.], [x, 225.]]
            assert row["display_bend"] == row["bend"]
            assert original_controls[
                "tail_lower_v_first_" + corner + "_widget"
            ]._phase6_menu.entrycget(1, "label") == row["label"]

        # Actual Tk dropdown command -> Engine preflight -> live 2D & T3D.
        chooser._phase6_menu.invoke(1)
        root.update_idletasks()
        root.update()
        if selected.get() != "V 型":
            from phase6_manufacturing_adapter import build_scene_payload_for_app
            from ae_engine.v_miter_factory_mother_check import _factory_original_shape
            from shapely.geometry import box
            payload = dict(build_scene_payload_for_app(designer, "tail"))
            payload["_use_committed_relief"] = False
            spec, _ctx = designer._part_spec_query_callback("tail", dict(payload))
            render = designer._scene_query_callback("tail", dict(payload))
            factory, width, height, _bends = _factory_original_shape(spec)
            removed = box(0., 0., width, height).difference(factory)
            components = ((removed,) if removed.geom_type == "Polygon"
                          else tuple(getattr(removed, "geoms", ())))
            from ae_engine.sheetmetal_drawing import LinePrimitive
            def bend_rows(scene):
                return tuple(sorted((
                    tuple(round(float(v), 7) for v in (
                        p.p1.x, p.p1.y, p.p2.x, p.p2.y
                    )) for p in scene.primitives
                    if isinstance(p, LinePrimitive) and p.layer == "BEND"
                )))
            solved = _real_resolved_tail(designer)
            raw_bends, solved_bends = bend_rows(render.scene), bend_rows(solved.scene)
            pytest.fail(
                f"Native V refused: {designer.settings_status_var.get()}"
                f"; raw_bounds={render.material.bounds};"
                f" source_bends={raw_bends}; resolved_bends={solved_bends};"
                f" exact_source_bends={tuple(repr(row) for row in render.scene.primitives if isinstance(row, LinePrimitive) and row.layer == 'BEND')};"
                f" exact_resolved_bends={tuple(repr(row) for row in solved.scene.primitives if isinstance(row, LinePrimitive) and row.layer == 'BEND')};"
                f" removed_components={tuple((v.bounds,round(v.area,5)) for v in components)}"
            )
        assert selected.get() == "V 型"
        assert designer._phase6_input_snapshot[api.TAIL_LOWER_V_SNAPSHOT_KEY] == "v90"
        with_v = _real_resolved_tail(designer)
        _assert_same_holes(original, with_v)
        # The Vault fixed 4x4 square uses the original sheet left/bottom
        # datum from Advanced Settings, not the stretched 48mm fold station.
        from ae_engine import ae
        from ae_engine.sheetmetal_drawing import PolylinePrimitive
        fixed = ae.VAULT_ENDCAP_FEATURE_POLICY
        expected_square = (
            fixed.square_hole_origin.x,
            fixed.square_hole_origin.y,
            fixed.square_hole_origin.x + fixed.square_hole_size.x,
            fixed.square_hole_origin.y + fixed.square_hole_size.y,
        )
        matching_square = [
            item for item in with_v.scene.primitives
            if isinstance(item, PolylinePrimitive)
            and item.layer == "CUTTING" and item.closed
            and len(item.points) == 4
            and all(abs(a-b) < 1e-7 for a,b in zip((
                min(pt.x for pt in item.points),
                min(pt.y for pt in item.points),
                max(pt.x for pt in item.points),
                max(pt.y for pt in item.points),
            ), expected_square))
        ]
        assert len(matching_square) == 1, (
            "VAULT_NATIVE_V48_FIXED_SQUARE_NOT_AT_SHEET_DATUM",
            expected_square,
        )
        assert with_v.metadata["tail_lower_v_preview_only"] is True
        visible_lines = api.project_operator_tail_lower_v_first_bend_options(
            live_spec, live_raw, active_v_render_data=with_v,
        )
        assert visible_lines["source_bends"] == source_lines["source_bends"]
        v_page = designer.settings_panel.render_context("tail")
        v_controls = v_page["extension_state"]
        for corner, x in (("bottom_left", 15.), ("bottom_right", 627.)):
            row = visible_lines[corner]["x"]
            assert row["bend"] == source_lines[corner]["x"]["bend"]
            assert row["display_bend"] == [[x, 0.], [x, 225.]]
            assert v_controls[
                "tail_lower_v_first_" + corner + "_widget"
            ]._phase6_menu.entrycget(1, "label") == row["label"]
            assert visible_lines[corner]["y"] == {
                **source_lines[corner]["y"],
                "display_bend": source_lines[corner]["y"]["bend"],
            }
        mesh = api.project_independent_part_view_mesh(
            "tail", with_v, x_profile=(), y_profile=(), thickness=2.,
        )
        assert mesh.triangles == api.tail_lower_v_preview_mesh(with_v)
        assert len(mesh.triangles) > 500
        if operator_first_axis is not None:
            # Real Tk Settings: each corner has a separate source-bound
            # finite BEND dropdown and an explicit commit control.
            page = designer.settings_panel.render_context("tail")
            extension = page["extension_state"]
            from phase6_manufacturing_adapter import build_scene_payload_for_app
            source = dict(build_scene_payload_for_app(designer, "tail"))
            source["_use_committed_relief"] = False
            spec, _ = designer._part_spec_query_callback("tail", source)
            raw = designer._scene_query_callback("tail", source)
            options = api.project_operator_tail_lower_v_first_bend_options(
                spec, raw, active_v_render_data=with_v,
            )
            for corner in ("bottom_left", "bottom_right"):
                var = extension["tail_lower_v_first_"+corner+"_var"]
                chooser_axis = extension["tail_lower_v_first_"+corner+"_widget"]
                assert chooser_axis.winfo_exists()
                assert var.get() == "未指定"
                # Invoke the REAL Tk dropdown, never bypass the button.
                chooser_axis._phase6_menu.invoke(
                    1 if operator_first_axis == "x" else 2
                )
                assert var.get() == options[corner][operator_first_axis]["label"]
            confirm = extension["tail_lower_v_first_confirm_widget"]
            assert confirm.winfo_exists()
            confirm.invoke()
            root.update_idletasks()
            root.update()
            saved_first = designer._phase6_input_snapshot[
                api.TAIL_LOWER_V_FIRST_BENDS_KEY
            ]
            assert saved_first["bottom_left"]["first"] == operator_first_axis
            assert saved_first["bottom_right"]["first"] == operator_first_axis
            with_v = _real_resolved_tail(designer)
            assert (with_v.metadata["tail_lower_v_operator_first_axis"]
                    == operator_first_axis)
            assert api.tail_lower_v_first_stage_mesh(with_v)
            assert api.tail_lower_v_preview_mesh(with_v)
        else:
            assert with_v.metadata["tail_lower_v_operator_first_axis"] is None
            assert api.tail_lower_v_first_stage_mesh(with_v) is None

        # Invoke WHD's actual main toolbar Save As and Open buttons.
        main.project_save_as_button.invoke()
        assert destination.is_file()
        saved = read_project(destination)["snapshot"]
        assert saved[api.TAIL_LOWER_V_SNAPSHOT_KEY] == "v90"
        assert feature in saved["part_features"]["tail"]
        if operator_first_axis is None:
            assert api.TAIL_LOWER_V_FIRST_BENDS_KEY not in saved
        else:
            assert saved[api.TAIL_LOWER_V_FIRST_BENDS_KEY][
                "bottom_left"
            ]["first"] == operator_first_axis
            assert saved[api.TAIL_LOWER_V_FIRST_BENDS_KEY][
                "bottom_right"
            ]["first"] == operator_first_axis

        main.project_open_button.invoke()
        root.update_idletasks()
        root.update()
        reopened = main.fold_designer_app or main.open_original_fold_designer()
        chooser2, selected2 = _real_tail_selector(reopened)
        assert selected2.get() == "V 型"
        reloaded_v = _real_resolved_tail(reopened)
        assert reloaded_v.metadata["tail_lower_v_operator_first_axis"] == operator_first_axis
        if operator_first_axis is None:
            assert api.tail_lower_v_first_stage_mesh(reloaded_v) is None
        else:
            assert api.tail_lower_v_first_stage_mesh(reloaded_v) == (
                api.tail_lower_v_first_stage_mesh(with_v)
            )
        _assert_same_holes(with_v, reloaded_v)
        reopened_page = reopened.settings_panel.render_context("tail")
        reopened_controls = reopened_page["extension_state"]
        assert reopened_controls[
            "tail_lower_v_first_bottom_left_widget"
        ]._phase6_menu.entrycget(1, "label") == visible_lines[
            "bottom_left"
        ]["x"]["label"]
        assert reloaded_v.material.symmetric_difference(with_v.material).area < 1e-5
        assert api.project_independent_part_view_mesh(
            "tail", reloaded_v, x_profile=(), y_profile=(), thickness=2.,
        ).triangles == api.tail_lower_v_preview_mesh(reloaded_v)

        chooser2._phase6_menu.invoke(0)
        root.update_idletasks()
        root.update()
        assert selected2.get() == "原樣"
        assert api.TAIL_LOWER_V_SNAPSHOT_KEY not in reopened._phase6_input_snapshot
        assert api.TAIL_LOWER_V_FIRST_BENDS_KEY not in reopened._phase6_input_snapshot
        restored = _real_resolved_tail(reopened)
        _assert_same_holes(original, restored)
        assert restored.material.symmetric_difference(original.material).area < 1e-5
        assert api.tail_lower_v_preview_mesh(restored) is None
        original_again = reopened.settings_panel.render_context("tail")
        for corner in ("bottom_left", "bottom_right"):
            assert original_again["extension_state"][
                "tail_lower_v_first_" + corner + "_widget"
            ]._phase6_menu.entrycget(1, "label") == source_lines[
                corner
            ]["x"]["label"]
    finally:
        root.destroy()
