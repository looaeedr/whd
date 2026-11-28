"""Complete native Open replaces a reused Vault Designer's catalog owner."""
from copy import deepcopy
import tkinter as tk
from tkinter import filedialog, messagebox

import pytest

from ae_engine import manufacturing_api as api
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_project_file import PROJECT_SCHEMA, write_project
from tests.test_issue3414_custom_source_owner import _receipt


def test_reused_vault_designer_full_open_replaces_custom_catalog(tmp_path, monkeypatch):
    from gui import Phase6PrimaryApplication

    root = tk.Tk()
    root.geometry('1400x900+0+0')
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        initial = host._compose_phase6_project_snapshot_from_main_gui()
        assert initial['model'] == '金庫型'
        from phase6_fold_profiles import build_box_body_profile
        initial['box_body_profile'] = build_box_body_profile(initial)
        initial['workspace']['box_body_profile'] = deepcopy(initial['box_body_profile'])
        key = 'custom:1'

        def saved(name, span=None):
            snap = deepcopy(initial)
            ws = Phase6DesignerWorkspace.from_snapshot(snap)
            if span is not None:
                assert ws.add_custom_part(display_name='同名板', fold_axis='X',
                                          transverse_length=span) == key
            state = ws.snapshot()
            for field in ('existing_parts', 'active_part', 'part_profiles', 'part_features', 'custom_parts'):
                if field in state:
                    snap[field] = deepcopy(state[field])
                    snap['workspace'][field] = deepcopy(state[field])
                else:
                    snap.pop(field, None)
                    snap['workspace'].pop(field, None)
            return write_project(tmp_path / (name + '.p6fold'),
                                 {'schema': PROJECT_SCHEMA, 'snapshot': snap})

        paths = (saved('a', 240), saved('b', 300), saved('empty'))
        owner_workspace = app.designer_workspace

        def open_file(path):
            monkeypatch.setattr(filedialog, 'askopenfilename', lambda **kw: str(path))
            errors = []
            monkeypatch.setattr(messagebox, 'showerror', lambda *args, **kw: errors.append(args))
            app.project_file_menu.invoke(0)
            assert not errors, errors
            root.update()
            assert host.project_controller.project_path == str(path)
            assert host.fold_designer_app is app
            assert app.designer_workspace is owner_workspace
            return host._compose_phase6_project_snapshot_from_main_gui(), app.designer_workspace.snapshot()

        def check_current(path, span):
            main, state = open_file(path)
            main_catalog = api.resolve_custom_part_catalog(main)
            designer_catalog = api.resolve_custom_part_catalog(state)
            assert main_catalog.get(key)['transverse_length'] == span
            assert designer_catalog.get(key) is not None, 'reused Designer retained the previous catalog'
            assert designer_catalog.get(key)['transverse_length'] == span
            assert main_catalog.snapshot() == designer_catalog.snapshot()
            assert key in app.available_parts
            assert api.resolve_custom_part_catalog(app._phase6_input_snapshot).snapshot() == designer_catalog.snapshot()
            live = {**app._phase6_input_snapshot, **state, 'workspace': state}
            receipt = _receipt(live, key)
            assert receipt.owner_id == main_catalog.get(key)['physical_owner_id']
            assert receipt.output_capability == 'check_only'
            api.open_workspace_owner_marking_draft(live, receipt)
            return live, receipt

        _, a = check_current(paths[0], 240)
        live_b, b = check_current(paths[1], 300)
        assert a.owner_id != b.owner_id
        assert a.source_sha256 != b.source_sha256
        with pytest.raises(ValueError, match='ROOT_MARKING_OWNER_STALE'):
            api.open_workspace_owner_marking_draft(live_b, a)

        # Partial workspace updates must not behave like a full file Open.
        before = api.resolve_custom_part_catalog(host.workspace_controller.workspace_snapshot()).snapshot()
        committed = host.workspace_controller.commit_workspace({'active_part': 'box_body'})
        assert api.resolve_custom_part_catalog(committed).snapshot() == before
        assert before['items'][key]['physical_owner_id'] == b.owner_id
        assert app.designer_workspace.custom_part(key)['physical_owner_id'] == b.owner_id

        main, state = open_file(paths[2])
        for snap in (main, state, app._phase6_input_snapshot):
            assert api.resolve_custom_part_catalog(snap).snapshot()['items'] == {}
            assert api.resolve_workspace_physical_root_owner(snap, key) is None
        assert key not in app.available_parts
        assert app.designer_workspace.custom_part(key) is None
        live_empty = {**app._phase6_input_snapshot, **state, 'workspace': state}
        for receipt in (a, b):
            with pytest.raises(ValueError, match='ROOT_MARKING_OWNER_STALE'):
                api.open_workspace_owner_marking_draft(live_empty, receipt)
    finally:
        root.destroy()
