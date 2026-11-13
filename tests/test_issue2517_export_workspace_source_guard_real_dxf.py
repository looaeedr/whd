"""#2517: GUI export source witness covers saved Workspace hole/part changes.

Only the Engine owns physical composition, genuine CUTTING/BEND and DXF
staging/reopen; the GUI supplies an immutable current-source revision witness.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project.export_actions import _current_authoritative_export_guard
from tests.test_issue2690_composed_panel_dxf import _flat, _geometry


class Workspace:
    def __init__(self, source):
        self.source = deepcopy(source)

    def snapshot(self):
        return deepcopy(self.source)


def _designer(snapshot, workspace):
    return SimpleNamespace(
        _phase6_input_snapshot=deepcopy(snapshot),
        designer_workspace=workspace,
    )


def _one_real_door_panel():
    return (("P1", _geometry(("door", _flat("door", width=120, hole=True)))),)


def test_workspace_hole_change_cannot_reuse_unchanged_top_level_input_revision():
    snapshot = {"model": "金庫型", "w": 800.0, "h": 1200.0, "t": 2.0}
    workspace = Workspace({"part_features": {"door": []}, "fold_profiles": {"door": []}})
    designer = _designer(snapshot, workspace)
    witness = _current_authoritative_export_guard(designer, snapshot)
    witness()
    previous_input = deepcopy(designer._phase6_input_snapshot)
    workspace.source["part_features"]["door"].append({"source": "new confirmed hole"})
    with pytest.raises(ValueError, match="DXF 工作區來源已變更"):
        witness()
    assert designer._phase6_input_snapshot == previous_input


def test_replaced_workspace_cannot_bypass_earlier_physical_source_witness():
    snapshot = {"model": "金庫型", "w": 800.0}
    original = Workspace({"part_features": {"door": []}})
    designer = _designer(snapshot, original)
    witness = _current_authoritative_export_guard(designer, snapshot)
    designer.designer_workspace = Workspace({"part_features": {"door": []}})
    with pytest.raises(ValueError, match="DXF 工作區來源已變更"):
        witness()


def test_legacy_no_workspace_keeps_original_input_guard():
    snap = {"model": "金庫型", "w": 800.0}
    designer = _designer(snap, None)
    witness = _current_authoritative_export_guard(designer, snap)
    witness()
    designer._phase6_input_snapshot["w"] = 900.0
    with pytest.raises(ValueError, match="DXF 出圖來源已變更"):
        witness()


def test_project_save_reload_plus_real_composed_dxf_reopen_and_atomic_source_guard(
    tmp_path,
):
    import phase6_project_file as project

    original = {
        "model": "金庫型", "w": 800.0, "h": 1200.0, "d": 350.0,
        "t": 2.0, "fw": 25.0,
        "part_features": {"door": []},
    }
    p = project.write_project(
        tmp_path / "hole-owner.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    reloaded = project.read_project(p)["snapshot"]
    assert "part_features" in reloaded
    assert reloaded["part_features"]["door"] == []
    stored = deepcopy(reloaded)
    workspace = Workspace({"part_features": reloaded["part_features"]})
    designer = _designer(reloaded, workspace)
    witness = _current_authoritative_export_guard(designer, reloaded)
    panels = _one_real_door_panel()
    target = tmp_path / "real-mfg.dxf"

    receipt = api.save_composed_panel_dxf(
        panels, target, pre_commit_guard=witness,
    )
    assert receipt.path == str(target)
    entities = tuple(ezdxf.readfile(target).modelspace())
    assert any(x.dxf.layer == "CUTTING" and x.dxftype() == "CIRCLE"
               for x in entities)
    assert any(x.dxf.layer == "BEND" for x in entities)
    assert reloaded == stored

    retained = target.read_bytes()
    calls = []

    def concurrent_hole_edit_after_staging():
        calls.append("verify")
        if len(calls) == 2:
            workspace.source["part_features"]["door"].append(
                {"source": "hole changed while exporting"}
            )
        witness()

    with pytest.raises(ValueError, match="DXF 工作區來源已變更"):
        api.save_composed_panel_dxf(
            panels, target, pre_commit_guard=concurrent_hole_edit_after_staging,
            overwrite=True,
        )
    assert calls == ["verify", "verify"]
    assert target.read_bytes() == retained
    assert tuple(ezdxf.readfile(target).modelspace())
    assert reloaded == stored


def test_unreadable_workspace_during_export_cannot_publish_unverified_dxf(
    tmp_path,
):
    snap = {"model": "金庫型", "w": 800.0}
    workspace = Workspace({"part_features": {"door": []}})
    designer = _designer(snap, workspace)
    witness = _current_authoritative_export_guard(designer, snap)

    def failure():
        raise OSError("Workspace source no longer readable")

    workspace.snapshot = failure
    target = tmp_path / "unverified.dxf"
    with pytest.raises(OSError, match="Workspace source no longer readable"):
        api.save_composed_panel_dxf(
            _one_real_door_panel(), target, pre_commit_guard=witness,
        )
    assert not target.exists()


class _RawMode:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _export_operator_intent(mode, monkeypatch):
    from gui_modules.project import export_actions as gui

    # Only mock the selected physical inventory; keep the real GUI witness,
    # Engine source guards and staging/DXF writer below.
    monkeypatch.setattr(gui, "_selected_export_flags", lambda *_a, **_kw:
                        {"head": True})
    selector = _RawMode(mode)
    host = SimpleNamespace(
        get_float_values=lambda: {
            "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0,
        },
        door_layout_columns=None,
        _phase6_current_existing_parts=lambda: ("head",),
        _has_any_indicator_box=lambda: False,
        receiving_dxf_group_mode_var=selector,
    )
    return host, selector


def test_export_witness_includes_gui_group_mode_before_modal_dialog(monkeypatch):
    from gui_modules.project import export_actions as gui

    host, selector = _export_operator_intent("ALL", monkeypatch)
    captured = gui._selected_dxf_live_operator_sources(host)
    assert captured["controls"]["receiving_group_mode"] == "ALL"

    source = {"model": "受電箱", "w": 800.0, "h": 1600.0, "t": 2.0}
    designer = _designer(source, Workspace({"part_features": {"head": []}}))
    witness = gui._current_authoritative_export_guard(
        designer, source, operator_source=captured,
        operator_source_reader=lambda: gui._selected_dxf_live_operator_sources(host),
    )
    witness()
    selector.value = "END_VS_MIDDLE"  # Changed during Folder dialog.
    with pytest.raises(ValueError, match="DXF 即時操作來源已變更"):
        witness()
    assert designer._phase6_input_snapshot == source


def test_actual_project_reload_and_reopened_dxf_group_intent_is_source_locked(
    tmp_path, monkeypatch,
):
    from gui_modules.project import export_actions as gui
    import phase6_project_file as project

    snapshot = {
        "model": "受電箱", "w": 800.0, "h": 1600.0,
        "d": 350.0, "t": 2.0, "fw": 25.0,
        "part_features": {"head": []},
    }
    saved = project.write_project(
        tmp_path / "real-grouped-operator.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": snapshot},
    )
    source = project.read_project(saved)["snapshot"]
    original = deepcopy(source)
    host, selector = _export_operator_intent("ALL", monkeypatch)
    workspace = Workspace({"part_features": source["part_features"]})
    designer = _designer(source, workspace)
    witness = gui._current_authoritative_export_guard(
        designer, source,
        operator_source=gui._selected_dxf_live_operator_sources(host),
        operator_source_reader=lambda: gui._selected_dxf_live_operator_sources(host),
    )
    target = tmp_path / "real-operator-mfg.dxf"
    panels = _one_real_door_panel()
    first = api.save_composed_panel_dxf(
        panels, target, pre_commit_guard=witness,
    )
    assert first.path == str(target)
    assert any(entity.dxf.layer == "CUTTING"
               for entity in ezdxf.readfile(target).modelspace())
    assert any(entity.dxf.layer == "BEND"
               for entity in ezdxf.readfile(target).modelspace())
    retained = target.read_bytes()

    checks = []

    def edit_group_during_staging():
        checks.append("precommit")
        if len(checks) == 2:
            selector.value = "END_VS_MIDDLE"
        witness()

    with pytest.raises(ValueError, match="DXF 即時操作來源已變更"):
        api.save_composed_panel_dxf(
            panels, target, pre_commit_guard=edit_group_during_staging,
            overwrite=True,
        )
    assert checks == ["precommit", "precommit"]
    assert target.read_bytes() == retained
    assert source == original


def test_legacy_no_group_mode_still_has_stable_none_witness(monkeypatch):
    from gui_modules.project import export_actions as gui

    host, _selector = _export_operator_intent("ALL", monkeypatch)
    del host.receiving_dxf_group_mode_var
    captured = gui._selected_dxf_live_operator_sources(host)
    assert captured["controls"]["receiving_group_mode"] is None
    source = {"model": "金庫型", "w": 800.0}
    designer = _designer(source, None)
    witness = gui._current_authoritative_export_guard(
        designer, source,
        operator_source=captured,
        operator_source_reader=lambda: gui._selected_dxf_live_operator_sources(host),
    )
    witness()
    assert source == designer._phase6_input_snapshot


def test_unreadable_group_mode_control_never_fabricates_export_selection(monkeypatch):
    from gui_modules.project import export_actions as gui

    host, selector = _export_operator_intent("ALL", monkeypatch)
    source = {"model": "受電箱", "w": 800.0}
    designer = _designer(source, None)
    witness = gui._current_authoritative_export_guard(
        designer, source,
        operator_source=gui._selected_dxf_live_operator_sources(host),
        operator_source_reader=lambda: gui._selected_dxf_live_operator_sources(host),
    )
    selector.get = lambda: (_ for _ in ()).throw(ValueError("bad group source"))
    with pytest.raises(ValueError, match="bad group source"):
        witness()
