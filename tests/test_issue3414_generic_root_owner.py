"""The explicit root transaction is distinct from projection and scope."""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from phase6_project_file import read_project
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet


KEY = api.ROOT_PHYSICAL_OCCUPANCY_KEY
SOURCE = Path(__file__).parent / "fixtures/issue1503_legacy_receiving_without_nfb_base.p6fold"


def _current(workspace, key, family="金庫型"):
    return api.resolve_workspace_physical_root_owner(
        {"model": family, **workspace.snapshot()}, key,
    )


def test_explicit_root_owner_creation_does_not_require_set_or_bay():
    state = api.SharedWorkspaceState()
    state.set_existing_parts(("head", "box_body:back", "base_plate_c1_r1"), active_repair="none")
    assert KEY not in state.snapshot()
    state.set_part_presence("head", False, active_repair="none")
    for key in ("head", "tail", "door", "base_plate", "indicator_box", "indicator_door"):
        state.set_part_presence(key, True, active_repair="none", explicit_root_source="金庫型")
    keys = set(state.snapshot()[KEY])
    assert keys == {"head", "tail", "door", "base_plate", "indicator_box", "indicator_door"}
    ids = {_current(state, key) for key in keys}
    assert None not in ids and len(ids) == len(keys)
    assert not _current(state, "box_body")
    assert not _current(state, "box_body:back")
    assert not _current(state, "base_plate_c1_r1")
    alias_source = {"model": "金庫型", "multi_door_enabled": True}
    assert not api.resolve_workspace_physical_root_owner({**state.snapshot(), **alias_source}, "door")
    alias = api.SharedWorkspaceState()
    alias.set_part_presence("door", True, active_repair="none", explicit_root_source=alias_source)
    assert KEY not in alias.snapshot()
    initial = _current(state, "tail")
    state.set_existing_parts(state.snapshot()["existing_parts"], active_repair="first")
    assert _current(state, "tail") == initial
    state.set_part_presence("tail", False, active_repair="none")
    state.set_part_presence("tail", True, active_repair="none")  # derived refresh is not operator Add
    assert not _current(state, "tail")
    state.set_part_presence("tail", False, active_repair="none")
    state.set_part_presence("tail", True, active_repair="none", explicit_root_source="金庫型")
    assert _current(state, "tail") not in ids
    state.reconcile_root_occupancy_family("受電箱")
    assert KEY not in state.snapshot()


def test_project_codec_rejects_conflicts_and_keeps_scoped_donor():
    from tests.test_issue3414_scoped_marking_proto import _ids, _real_source
    state = api.SharedWorkspaceState()
    state.set_part_presence("tail", True, active_repair="none", explicit_root_source="受電箱")
    source = _real_source()
    donor = _ids(source)
    snapshot = {**source, "existing_parts": list(state.existing_parts), KEY: state.snapshot()[KEY]}
    claim = api.normalize_project_snapshot_authority(snapshot)
    assert _ids(claim) == donor
    assert api.resolve_workspace_physical_root_owner(claim, "tail") == state.snapshot()[KEY]["tail"]["owner_id"]
    assert api.resolve_workspace_physical_root_owner(claim, "base_plate") is None
    with pytest.raises(ValueError, match="OCCUPANCY_CONFLICT"):
        api.normalize_project_snapshot_authority({**snapshot, "workspace": {KEY: {}}})
    with pytest.raises(ValueError, match="OCCUPANCY_INVALID"):
        api.normalize_project_snapshot_authority({**snapshot, KEY: {"tail": {"owner_id": "tail", "family": "受電箱"}}})


def test_primary_project_save_open_replaces_only_removed_root(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog
    from gui import Phase6PrimaryApplication

    root = tk.Tk()
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        menu = app.project_file_menu

        def open_file(path):
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
            menu.invoke(0)
            root.update()
            assert host.project_controller.project_path == str(path)

        def save(name):
            path = tmp_path / (name + ".p6fold")
            monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(path))
            menu.invoke(2)
            root.update()
            return path, read_project(path)["snapshot"]

        open_file(SOURCE)
        assert KEY not in app.designer_workspace.snapshot()
        for key in ("head", "tail", "door"):
            if key in app.designer_workspace.available_parts:
                assert app.remove_part(key)
                root.update()
            app.add_part(key)
            root.update()
        initial = app.designer_workspace.snapshot()[KEY]
        assert set(initial) == {"head", "tail", "door"}
        assert len({entry["owner_id"] for entry in initial.values()}) == 3
        old, saved = save("with-roots")
        assert saved[KEY] == initial
        for key in initial:
            assert api.resolve_workspace_physical_root_owner(saved, key) == initial[key]["owner_id"]
        open_file(old)
        assert app.designer_workspace.snapshot()[KEY] == initial
        assert app.remove_part("head")
        root.update()
        deleted, saved = save("head-removed")
        assert set(saved[KEY]) == {"tail", "door"}
        assert api.resolve_workspace_physical_root_owner(saved, "head") is None
        open_file(deleted)
        app.add_part("head")
        root.update()
        replacement, saved = save("head-replaced")
        assert saved[KEY]["head"]["owner_id"] != initial["head"]["owner_id"]
        assert all(saved[KEY][key] == initial[key] for key in ("tail", "door"))
        open_file(replacement)
        assert saved[KEY] == app.designer_workspace.snapshot()[KEY]
        app.baseline_model_var.set("金庫型")
        root.update()
        assert app._phase6_input_snapshot["model"] == "金庫型"
        assert KEY not in app.designer_workspace.snapshot()
        app.baseline_model_var.set("受電箱")
        root.update()
        assert app._phase6_input_snapshot["model"] == "受電箱"
        assert KEY not in app.designer_workspace.snapshot()
        assert KEY not in save("family-round-trip-retired")[1]
        open_file(SOURCE)
        assert KEY not in app.designer_workspace.snapshot()
        _, other = save("legacy-cannot-inherit-other-project")
        assert not other.get(KEY)
    finally:
        root.destroy()


def test_legacy_owner_proposal_requires_first_valid_selected_stock_mark(actual_sheet):
    from dataclasses import replace
    from ae_engine.contracts import ManufacturingContext
    from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import _part_spec

    configured, _, physical, midpoint, angle = actual_sheet
    _, spec = _part_spec(configured)
    source = {**configured, "existing_parts": ["box_body", "base_plate"]}
    draft = api.open_physical_sheet_marking("base_plate", context=physical)
    mark = api.create_physical_sheet_mark(
        draft, (), midpoint=midpoint, length=12, angle_deg=angle,
    )
    kwargs = dict(selected_spec=spec, manufacturing_context=ManufacturingContext(),
                  current=draft, opened=draft)
    assert KEY not in source
    with pytest.raises(ValueError, match="FIRST_MARK_REQUIRED"):
        api.propose_legacy_root_occupancy_for_mark_confirm(source, features=(), **kwargs)
    wrong = replace(spec, width=spec.width + 20)
    with pytest.raises(ValueError, match="SOURCE_STALE"):
        api.propose_legacy_root_occupancy_for_mark_confirm(
            source, features=(mark,), **{**kwargs, "selected_spec": wrong},
        )
    new = api.propose_legacy_root_occupancy_for_mark_confirm(source, features=(mark,), **kwargs)
    assert KEY not in source  # detached; no ownership created by preview or opening
    assert api.resolve_workspace_physical_root_owner({**source, KEY: new}, "base_plate")
