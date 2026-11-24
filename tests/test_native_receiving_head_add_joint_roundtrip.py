"""A newly added Receiving EndCap uses the persisted Joint source immediately."""
from dataclasses import replace
import ezdxf

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.manufacturing_equivalence import ManufacturingParameters, manufacturing_equivalence_payload
from ae_engine.manufacturing_export import resolved_physical_render_parts
from phase6_manufacturing_adapter import build_scene_payload_for_app
from phase6_project_file import read_project
from tests.test_issue3414_scoped_marking_proto import _raw_write, _real_source, _resize


def test_native_receiving_add_has_same_joint_stock_before_first_save_and_open(tmp_path, monkeypatch):
    key = "head"
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from gui import Phase6PrimaryApplication

    source = _resize(_real_source(), 1)
    source["existing_parts"] = ["box_body", "base_plate"]
    initial = _raw_write(tmp_path / "initial.p6fold", source)
    saved = tmp_path / "added.p6fold"
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = Phase6PrimaryApplication(root)
        errors = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, text, **kw: errors.append(text))
        host.load_phase6_project(initial, open_designer=True)
        root.update()
        app = host.fold_designer_app
        assert key not in app.designer_workspace.available_parts

        def all_flats():
            active = host.fold_designer_app
            return dict(resolved_physical_render_parts(active._phase6_resolve_manufacturing_geometry()))

        def signature(render, *, material_only=False):
            if material_only:
                # The assembly can legitimately add frame MARKING; compare
                # structural cutting, holes and finite folds independently.
                scene = DrawingScene([p for p in render.scene.primitives
                                      if p.layer in {"CUTTING", "BEND", "BLIND_HOLE"}])
                render = replace(render, scene=scene)
            return manufacturing_equivalence_payload(render, ManufacturingParameters("actual Receiving", 2, None))

        unaffected = signature(all_flats()["base_plate"])

        def measure(stage):
            app = host.fold_designer_app
            request = build_scene_payload_for_app(app, key)
            spec, context = host._fold_designer_part_spec_from_payload(key, request)
            assert len([j for j in request["assembly_joints"] if j["subject_part"] == key]) == 4
            assert len(spec.resolved_assembly_relief_cuts) == 2
            direct = api.build_part_render_data(spec, context)
            actual = all_flats()
            assert signature(actual["base_plate"]) == unaffected
            assert signature(actual[key], material_only=True) == signature(direct, material_only=True)
            target = tmp_path / (stage + ".dxf")
            host._export_authoritative_part(spec, target, replace(context, overwrite=True))
            assert ezdxf.readfile(target).header["$INSUNITS"] == 4
            assert api.verify_saved_part_render_data_dxf(direct, target).ok
            return signature(direct), signature(actual[key])

        # Real operator Add menu action, not a direct project field mutation.
        app._refresh_add_part_menu()
        choices = [i for i in range(app.add_part_menu.index("end") + 1)
                   if app.add_part_menu.type(i) == "command"
                   and "封頭" in app.add_part_menu.entrycget(i, "label")]
        assert len(choices) == 1
        app.add_part_menu.invoke(choices[0])
        root.update()
        assert key in app.designer_workspace.available_parts
        before = measure("after-add")
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(saved))
        app.project_file_menu.invoke(2)
        root.update()
        assert not errors and saved.is_file()
        assert key in read_project(saved)["snapshot"]["existing_parts"]
        assert measure("after-save") == before
        host.load_phase6_project(saved, open_designer=True)
        root.update()
        host.fold_designer_app.activate_part(key)
        root.update()
        assert measure("after-open") == before
    finally:
        root.destroy()
