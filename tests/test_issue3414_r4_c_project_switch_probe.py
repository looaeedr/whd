from copy import deepcopy
import tkinter as tk
from tkinter import filedialog, messagebox

import ezdxf
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_scene_access import owner_render_data
from gui import Phase6PrimaryApplication
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_fold_profiles import build_box_body_profile
from phase6_project_file import PROJECT_SCHEMA, write_project
from tests.test_issue3414_custom_source_owner import _receipt
from tests.test_issue3414_saved_c_divider_source import KEY, actual_sources, full_request


def test_vault_custom_receiving_custom_and_c_then_empty(actual_sources, tmp_path, monkeypatch):
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **kw: errors.append(a))
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **kw: None)
    try:
        host = Phase6PrimaryApplication(root)
        vault = host._compose_phase6_project_snapshot_from_main_gui()
        vault["box_body_profile"] = build_box_body_profile(vault)
        vault["workspace"]["box_body_profile"] = deepcopy(vault["box_body_profile"])
        rec = actual_sources[0][0]
        key = "custom:1"

        def save(name, base, span=None):
            snap = deepcopy(base)
            state = Phase6DesignerWorkspace.from_snapshot(snap)
            if span is not None:
                assert state.add_custom_part(display_name="同名板", fold_axis="X", transverse_length=span) == key
            actual = state.snapshot()
            for field in ("existing_parts", "active_part", "part_profiles", "part_features", "custom_parts"):
                if field in actual:
                    snap[field] = deepcopy(actual[field])
                    snap["workspace"][field] = deepcopy(actual[field])
                else:
                    snap.pop(field, None)
                    snap["workspace"].pop(field, None)
            return write_project(tmp_path / (name + ".p6fold"), {"schema": PROJECT_SCHEMA, "snapshot": snap})

        a_path, b_path, empty_path = save("a", vault, 240), save("b", rec, 300), save("empty", vault)
        summaries = []

        def open_file(path):
            app = host.fold_designer_app
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
            app.project_file_menu.invoke(0)
            root.update()
            assert not errors, errors
            assert host.project_controller.project_path == str(path)
            app = host.fold_designer_app
            main = host._compose_phase6_project_snapshot_from_main_gui()
            state = app.designer_workspace.snapshot()
            observed = tuple(api.resolve_custom_part_catalog(x).snapshot() for x in (main, state, app._phase6_input_snapshot))
            summaries.append(tuple(v.get("items", {}).get(key, {}).get("transverse_length") for v in observed))
            assert observed[0] == observed[1] == observed[2], summaries
            return main, app, {**app._phase6_input_snapshot, **state, "workspace": state}

        _, _, live_a = open_file(a_path)
        a = _receipt(live_a, key)
        main, app, live_b = open_file(b_path)
        b = _receipt(live_b, key)
        assert a.owner_id != b.owner_id and a.source_sha256 != b.source_sha256
        with pytest.raises(ValueError, match="ROOT_MARKING_OWNER_STALE"):
            api.open_workspace_owner_marking_draft(live_b, a)
        saved_owner, saved_geometry = api.resolve_saved_receiving_c_divider_source(main, KEY)
        live_geometry = api.resolve_manufacturing_request(full_request(app)).geometry
        assert api.require_saved_receiving_c_divider_source(main, live_geometry, KEY) == saved_owner
        dxf = tmp_path / "c.dxf"
        saved_render = owner_render_data(saved_geometry, KEY)
        api.save_part_render_data_dxf(saved_render, dxf, verify_reopen=True)
        doc = ezdxf.readfile(dxf)
        assert doc.header["$INSUNITS"] == 4 and not doc.audit().errors
        assert api.verify_saved_part_render_data_dxf(owner_render_data(live_geometry, KEY), dxf).ok
        main, app, empty = open_file(empty_path)
        assert summaries == [(240, 240, 240), (300, 300, 300), (None, None, None)]
        for r in (a, b):
            with pytest.raises(ValueError, match="ROOT_MARKING_OWNER_STALE"):
                api.open_workspace_owner_marking_draft(empty, r)
        assert KEY not in app.available_parts
    finally:
        root.destroy()


def test_saved_c_rejects_dependent_custom_endpoint_and_conflicted_catalog(actual_sources):
    snap = deepcopy(actual_sources[0][0])
    state = Phase6DesignerWorkspace.from_snapshot(snap)
    key = state.add_custom_part(display_name="獨立折板", fold_axis="X", transverse_length=300)
    assert key == "custom:1"
    catalog = state.snapshot()["custom_parts"]
    snap["custom_parts"] = deepcopy(catalog)
    snap["workspace"]["custom_parts"] = deepcopy(catalog)
    owner, _ = api.build_saved_receiving_c_divider_request(snap, KEY)
    assert owner.owner_id
    for endpoint in ("subject_part", "target_part"):
        for spelling in (key, f" {key} "):
            dependent = deepcopy(snap)
            dependent["assembly_joints"][0][endpoint] = spelling
            with pytest.raises(ValueError, match="C_DIVIDER_SAVED_DEPENDENCY_SCOPE_UNVERIFIED"):
                api.build_saved_receiving_c_divider_request(dependent, KEY)
    for endpoint in ("subject_part", "target_part"):
        for provenance in ("LEGACY_MIGRATED", "USER_ADDED"):
            alias = deepcopy(snap)
            row = alias.pop("assembly_joints")[0]
            row.update({endpoint: f" {key} ", "source": provenance})
            alias.update(assembly_joint_schema_version=1, joints=[row])
            with pytest.raises(ValueError, match="C_DIVIDER_SAVED_DEPENDENCY_SCOPE_UNVERIFIED"):
                api.build_saved_receiving_c_divider_request(alias, KEY)
    user_joint = deepcopy(snap)
    user_joint["assembly_joints"][0]["source"] = "USER_ADDED"
    with pytest.raises(ValueError, match="C_DIVIDER_SAVED_DEPENDENCY_SCOPE_UNVERIFIED"):
        api.build_saved_receiving_c_divider_request(user_joint, KEY)
    snap["workspace"]["custom_parts"]["items"][key]["transverse_length"] += 1
    with pytest.raises(ValueError, match="CUSTOM_PART_CATALOG_CONFLICT"):
        api.build_saved_receiving_c_divider_request(snap, KEY)
