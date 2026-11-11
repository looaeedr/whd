"""#2517: final GUI DXF publish cannot outlive its original physical source.

These regressions reopen genuine Engine CUTTING/BEND DXFs; no GUI renderer,
manufacturing formula or second canonical geometry is introduced.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project import export_actions as export_gui
from tests.test_issue2690_composed_panel_dxf import _flat, _geometry


class _Workspace:
    def __init__(self, source):
        self.source = deepcopy(source)

    def snapshot(self):
        return deepcopy(self.source)


def _physical_panels(width):
    return (("P1", _geometry(("door", _flat("door", width=width)))),)


def _project_source(tmp_path):
    import phase6_project_file as project

    source = {
        "model": "金庫型", "w": 800.0, "h": 1200.0, "d": 350.0,
        "t": 2.0, "fw": 25.0, "part_features": {"door": []},
    }
    path = project.write_project(
        tmp_path / "publish-source.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    reopened = project.read_project(path)["snapshot"]
    assert reopened["part_features"] == source["part_features"]
    return reopened


def _host(source):
    workspace = _Workspace({"part_features": source["part_features"]})
    designer = SimpleNamespace(
        _phase6_input_snapshot=deepcopy(source),
        designer_workspace=workspace,
        _phase6_resolve_manufacturing_geometry=lambda: None,
    )
    host = SimpleNamespace(
        fold_designer_app=designer,
        _flush_phase6_authoritative_state=lambda: None,
        _phase6_current_existing_parts=lambda: ("door",),
        _has_any_indicator_box=lambda: False,
        get_float_values=lambda: {"t": 2.0},
        draw_stock_var=SimpleNamespace(get=lambda: False),
        receiving_dxf_group_mode_var=SimpleNamespace(get=lambda: "ALL"),
    )
    return host, workspace


def _run_real_gui_export(monkeypatch, host, folder, *, on_confirmation=None):
    events = []
    monkeypatch.setattr(export_gui, "_selected_export_flags",
                        lambda *_args: {"door": True})
    monkeypatch.setattr(export_gui, "_validate_selected_indicator_exports",
                        lambda *_args: None)
    monkeypatch.setattr(
        api, "plan_unconfigured_receiving_base_export_retry",
        lambda _errors, _flags: None,
    )
    monkeypatch.setattr(export_gui.filedialog, "askdirectory",
                        lambda **_kwargs: str(folder))

    def stage(_host, stage_folder, _values, _flags, _stock):
        receipt = api.save_composed_panel_dxf(
            _physical_panels(165.0),
            __import__("pathlib").Path(stage_folder) / "P1.dxf",
            pre_commit_guard=lambda: None,
        )
        assert receipt.path
        return ["P1.dxf"], []

    monkeypatch.setattr(export_gui, "_export_selected_parts", stage)

    def confirm(*_args, **_kwargs):
        events.append("overwrite_prompt")
        if on_confirmation is not None:
            on_confirmation()
        return True

    monkeypatch.setattr(export_gui.messagebox, "askyesno", confirm)
    monkeypatch.setattr(export_gui.messagebox, "showerror",
                        lambda _title, detail: events.append(("error", detail)))
    monkeypatch.setattr(export_gui.messagebox, "showinfo",
                        lambda _title, detail: events.append(("success", detail)))
    export_gui.export_selected_dxf(host)
    return events


def test_gui_overwrite_dialog_workspace_hole_change_cannot_publish_old_dxf(
    tmp_path, monkeypatch,
):
    saved = _project_source(tmp_path)
    unchanged = deepcopy(saved)
    host, workspace = _host(saved)
    target = tmp_path / "P1.dxf"
    api.save_composed_panel_dxf(
        _physical_panels(110.0), target, pre_commit_guard=lambda: None,
    )
    prior = target.read_bytes()

    def edit_after_engine_staging():
        workspace.source["part_features"]["door"].append(
            {"confirmed": "new physical hole after DXF staging"}
        )

    events = _run_real_gui_export(
        monkeypatch, host, tmp_path, on_confirmation=edit_after_engine_staging,
    )
    assert "overwrite_prompt" in events
    assert any(
        isinstance(event, tuple) and event[0] == "error"
        and "DXF 工作區來源已變更" in event[1] for event in events
    )
    assert not any(isinstance(event, tuple) and event[0] == "success"
                   for event in events)
    assert target.read_bytes() == prior
    reopened = tuple(ezdxf.readfile(target).modelspace())
    assert any(e.dxf.layer == "CUTTING" for e in reopened)
    assert any(e.dxf.layer == "BEND" for e in reopened)
    assert host.fold_designer_app._phase6_input_snapshot == unchanged
    assert saved == unchanged


def test_gui_publish_unchanged_source_writes_reopened_engine_dxf(
    tmp_path, monkeypatch,
):
    saved = _project_source(tmp_path)
    host, workspace = _host(saved)
    events = _run_real_gui_export(monkeypatch, host, tmp_path)
    assert any(isinstance(e, tuple) and e[0] == "success" for e in events)
    assert not any(isinstance(e, tuple) and e[0] == "error" for e in events)
    result = tuple(ezdxf.readfile(tmp_path / "P1.dxf").modelspace())
    assert any(e.dxf.layer == "CUTTING" for e in result)
    assert any(e.dxf.layer == "BEND" for e in result)
    assert workspace.snapshot()["part_features"] == saved["part_features"]


@pytest.mark.parametrize("drift_check", [2, 3])
def test_outer_publish_rolls_back_old_dxf_if_source_changes_during_move(
    tmp_path, drift_check,
):
    source = _project_source(tmp_path)
    designer, workspace = _host(source)
    witness = export_gui._current_authoritative_export_guard(
        designer.fold_designer_app, source,
    )
    stage_dir = tmp_path / "stage"
    stage_dir.mkdir()
    existing = tmp_path / "P1.dxf"
    api.save_composed_panel_dxf(
        _physical_panels(110.0), existing, pre_commit_guard=lambda: None,
    )
    api.save_composed_panel_dxf(
        _physical_panels(165.0), stage_dir / "P1.dxf",
        pre_commit_guard=lambda: None,
    )
    original = existing.read_bytes()
    count = 0

    def source_guard():
        nonlocal count
        count += 1
        if count == drift_check:
            workspace.source["part_features"]["door"].append(
                {"confirmed": "new source during publish"}
            )
        witness()

    with pytest.raises(ValueError, match="DXF 工作區來源已變更"):
        export_gui._commit_staged_project_export(
            stage_dir, tmp_path, pre_commit_guard=source_guard,
        )
    assert count == drift_check
    assert existing.read_bytes() == original
    assert any(e.dxf.layer == "CUTTING"
               for e in ezdxf.readfile(existing).modelspace())
    assert not tuple(tmp_path.glob(".whd-export-backup-*"))


def test_invalid_final_publish_guard_cannot_change_existing_dxf(tmp_path):
    stage_dir = tmp_path / "stage"
    stage_dir.mkdir()
    target = tmp_path / "P1.dxf"
    target.write_bytes(b"original-file")
    (stage_dir / "P1.dxf").write_bytes(b"new-file")
    with pytest.raises(TypeError, match="DXF_PRECOMMIT_SOURCE_GUARD_INVALID"):
        export_gui._commit_staged_project_export(
            stage_dir, tmp_path, pre_commit_guard="true",
        )
    assert target.read_bytes() == b"original-file"
