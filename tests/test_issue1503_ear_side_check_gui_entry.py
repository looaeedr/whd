# -*- coding: utf-8 -*-
"""#1503: real GUI export-action seam for SIDE CHECK-only DXF, never MFG."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from gui_modules.project import export_actions


def _host(snapshot, *, resolver=True):
    state = {"flushed": 0, "resolved": 0}
    def flush(): state["flushed"] += 1
    def resolve():
        state["resolved"] += 1
        return "REAL_RESOLVED_GEOMETRY"
    designer = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        _phase6_resolve_manufacturing_geometry=resolve if resolver else None,
    )
    return SimpleNamespace(
        _flush_phase6_authoritative_state=flush,
        fold_designer_app=designer,
    ), state


def _snapshot(**edits):
    return dict(
        model="受電箱", nfb_config_submitted=True, active_mode="set_bay",
        w=800., h=1600., d=350., t=2., **edits,
    )


def _dialogs(monkeypatch, path):
    events = []
    monkeypatch.setattr(export_actions.filedialog, "askdirectory",
                        lambda **kw: events.append(("select", kw["title"])) or str(path))
    monkeypatch.setattr(export_actions.messagebox, "showinfo",
                        lambda title, msg: events.append(("success", title, msg)))
    monkeypatch.setattr(export_actions.messagebox, "showerror",
                        lambda title, msg: events.append(("error", title, msg)))
    return events


def test_real_gui_selected_receiving_side_check_is_not_standard_manufacturing_export(
    tmp_path, monkeypatch,
):
    import ae_engine.receiving_fixed_plate_side_check_dxf as check
    host, state = _host(_snapshot())
    events = _dialogs(monkeypatch, tmp_path)
    calls = []
    def output(snap, geometry, folder, **kwargs):
        calls.append((snap, geometry, folder, kwargs))
        return SimpleNamespace(
            output_paths=(("box_body:left_side", "/tmp/LEFT_CHECK_ONLY.dxf"),
                          ("box_body:right_side", "/tmp/RIGHT_CHECK_ONLY.dxf")),
            part_ids=("EAR-L", "EAR-R"),
            marking_lines_verified=8,
            status="RECEIVING_EAR_SIDE_CHECK_DXF_ONLY",
            manufacturing_ready=False,
        )
    monkeypatch.setattr(check, "export_receiving_ear_side_check_only_dxf", output)
    result = export_actions.export_receiving_ear_side_check_dxf(host)
    assert result.status == "RECEIVING_EAR_SIDE_CHECK_DXF_ONLY"
    assert result.manufacturing_ready is False
    assert state == {"flushed": 1, "resolved": 1}
    assert len(calls) == 1
    assert calls[0][:3] == (_snapshot(), "REAL_RESOLVED_GEOMETRY", str(tmp_path))
    assert calls[0][3] == {
        "dimensions": (800., 1600., 350.),
        "sheet_thickness": 2.,
        "overwrite": False,
    }
    assert [x[0] for x in events] == ["select", "success"]
    assert "非製造" in events[-1][1]
    assert "8" in events[-1][2]


@pytest.mark.parametrize("updates", (
    {"model": "金庫型"},
    {"nfb_config_submitted": False},
    {"active_mode": "quantity"},
    {"w": 750.},
    {"t": 3.},
))
def test_no_check_dxf_picker_or_resolution_for_unapproved_or_wrong_mode(
    tmp_path, monkeypatch, updates,
):
    source = _snapshot()
    source.update(updates)
    host, state = _host(source)
    events = _dialogs(monkeypatch, tmp_path)
    assert export_actions.export_receiving_ear_side_check_dxf(host) is None
    assert state == {"flushed": 1, "resolved": 0}
    assert [row[0] for row in events] == ["error"]


def test_missing_canonical_designer_resolver_is_fail_closed(tmp_path, monkeypatch):
    host, state = _host(_snapshot(), resolver=False)
    events = _dialogs(monkeypatch, tmp_path)
    assert export_actions.export_receiving_ear_side_check_dxf(host) is None
    assert state["resolved"] == 0
    assert len(events) == 1 and events[0][0] == "error"


def test_cancel_file_picker_creates_no_check_artifact(tmp_path, monkeypatch):
    host, state = _host(_snapshot())
    events = _dialogs(monkeypatch, tmp_path)
    monkeypatch.setattr(export_actions.filedialog, "askdirectory", lambda **kw: "")
    assert export_actions.export_receiving_ear_side_check_dxf(host) is None
    assert state == {"flushed": 1, "resolved": 1}
    assert events == []


def test_saving_error_cannot_report_success_or_unlock_manufacturing(
    tmp_path, monkeypatch,
):
    import ae_engine.receiving_fixed_plate_side_check_dxf as check
    host, state = _host(_snapshot())
    events = _dialogs(monkeypatch, tmp_path)
    def fail(*args, **kwargs):
        raise ValueError("EAR_SIDE_CHECK_SAVED_DXF_ROUNDTRIP_FAILED")
    monkeypatch.setattr(check, "export_receiving_ear_side_check_only_dxf", fail)
    assert export_actions.export_receiving_ear_side_check_dxf(host) is None
    assert [x[0] for x in events] == ["select", "error"]
    assert "EAR_SIDE_CHECK" in events[-1][-1]
    assert "未放行正式製造" in events[-1][-1]


def test_gui_binding_and_left_panel_label_is_a_separate_action():
    import ast
    root = Path(__file__).resolve().parents[1]
    app = ast.parse((root / "gui.py").read_text(encoding="utf-8"))
    clazz = next(node for node in app.body
                 if isinstance(node, ast.ClassDef)
                 and node.name == "Phase6ApplicationHost")
    assigned = {
        target.id: ast.unparse(node.value)
        for node in clazz.body if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }
    assert assigned["export_receiving_ear_side_check_dxf"] == (
        "_phase6_project_export.export_receiving_ear_side_check_dxf"
    )
    assert assigned["export_selected_dxf"] == (
        "_phase6_project_export.export_selected_dxf"
    )
    view = (root / "gui_modules/layout/left_panel.py").read_text(encoding="utf-8")
    assert "受電箱固定片側板 CHECK DXF（非製造）" in view
    assert "command=host.export_receiving_ear_side_check_dxf" in view
    assert "command=host.export_selected_dxf" in view
