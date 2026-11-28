"""Primary project Open must share the certified corner source with Save/Reload."""
from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import ezdxf
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.composed_panel_dxf import _actual_signature
from gui import Phase6PrimaryApplication
from gui_modules.project.export_actions import export_selected_dxf
from gui_modules.project import export_actions
from phase6_manufacturing_adapter import build_scene_payload_for_app
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from tests.test_issue2517_direct_door_partspec_original_source_engine_gate import _row


KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")


def _standard():
    return {key: {"type_id": "CROSS", "rotation_quadrants": 0,
                  "cross_mode": "standard"} for key in KEYS}


def _registry(family):
    return {key: api.endcap_corner_selection_to_raw(value)
            for key, value in api.operator_known_model_corner_state(
                ("door",), cabinet_family=family)["door"].items()}


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_project_corner_source_fills_only_missing_known_parts(family):
    explicit = _standard()
    source = {"model": family, "corner_state": {"door": explicit}}
    before = deepcopy(source)
    assert api.project_operator_saved_project_corner_source(source, ("door",))["door"] == explicit
    assert source == before
    absent = {"model": family}
    assert api.project_operator_saved_project_corner_source(absent, ("door",))["door"] == _registry(family)
    assert absent == {"model": family}
    assert api.project_operator_saved_project_corner_source({"model": "自訂"}, ("door",)) == {}
    assert api.project_operator_saved_project_corner_source({"model": "UNKNOWN"}, ("door",)) == {}


def test_primary_vault_corner_source_explicit_and_absent_roundtrip(tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(export_actions.messagebox, "showerror", lambda *a, **kw: errors.append(a))
    monkeypatch.setattr(export_actions.messagebox, "showinfo", lambda *a, **kw: None)
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        owner = app.designer_workspace
        def open_file(path):
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
            app.project_file_menu.invoke(0)
            root.update()
            assert not errors, errors
            assert Path(host.project_controller.project_path) == path
            assert host.fold_designer_app is app and app.designer_workspace is owner
            app.activate_part("door")
            root.update()
        def physical_policy():
            spec, _ = app._part_spec_query_callback("door", build_scene_payload_for_app(app, "door"))
            return {key: api.endcap_corner_selection_to_raw(getattr(spec.corner_policy, key)) for key in KEYS}
        def signature(folder):
            folder.mkdir()
            for key in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
                getattr(host, f"export_{key}_var").set(key == "door")
            monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(folder))
            export_selected_dxf(host)
            assert not errors, errors
            path, = folder.glob("*.dxf")
            doc = ezdxf.readfile(path)
            assert doc.units == 4 and not doc.audit().errors
            return tuple(sorted(repr(_actual_signature(e)) for e in doc.modelspace()))
        certified = _registry("金庫型")
        # Canonical policy serialization may include normalized optional fields.
        standard = {key: api.endcap_corner_selection_to_raw(
            api.endcap_corner_selection_from_raw(raw)) for key, raw in _standard().items()}
        cases = (("absent", None, certified), ("retain", certified, certified),
                 ("standard", standard, standard), ("absent_after_explicit", None, certified))
        signatures = {}
        for name, explicit, expected in cases:
            row = _row()
            row.update(multi_door_enabled=False, existing_parts=["box_body", "base_plate", "door"])
            if explicit is not None:
                row["corner_state"] = {"door": explicit}
            path = write_project(tmp_path / f"{name}.p6fold", {"schema": PROJECT_SCHEMA, "snapshot": row})
            open_file(path)
            assert physical_policy() == expected
            before = signature(tmp_path / f"{name}-before")
            saved = tmp_path / f"{name}-saved.p6fold"
            monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(saved))
            app.project_file_menu.invoke(2)
            root.update()
            assert not errors and saved.is_file(), errors
            assert read_project(saved)["snapshot"]["corner_state"]["door"] == expected
            open_file(saved)
            assert physical_policy() == expected
            assert signature(tmp_path / f"{name}-after") == before
            signatures[name] = before
        assert signatures["absent"] == signatures["retain"] == signatures["absent_after_explicit"]
        assert signatures["standard"] != signatures["retain"]
    finally:
        root.destroy()
