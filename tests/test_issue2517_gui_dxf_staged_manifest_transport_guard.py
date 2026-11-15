"""#2517: selected GUI DXF publishes exactly verified Engine stage outputs.

The GUI must not turn a false Engine filename/partial stage into manufacturing
success or publish an unreported physical DXF. Real DXF bytes are produced and
independently reopened; the GUI still owns only transport/overwrite consent.
"""
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project import export_actions as gui
from tests.test_issue2517_gui_final_dxf_publish_source_guard import (
    _host, _physical_panels, _project_source,
)


def _run_export(monkeypatch, host, folder, *, variant):
    events = []
    monkeypatch.setattr(gui, "_selected_export_flags",
                        lambda *_: {"door": True})
    monkeypatch.setattr(gui, "_validate_selected_indicator_exports",
                        lambda *_: None)
    monkeypatch.setattr(
        api, "plan_unconfigured_receiving_base_export_retry",
        lambda *_: None,
    )
    monkeypatch.setattr(gui.filedialog, "askdirectory",
                        lambda **_: str(folder))

    def actual_engine(_ui, stage, _values, _flags, _stock):
        # A valid, already-manufactured canonical Engine DXF. Only the
        # transport filename report/stage inventory is altered here.
        api.save_composed_panel_dxf(
            _physical_panels(165.0), Path(stage) / "P1.dxf",
            pre_commit_guard=lambda: None,
        )
        if variant == "unreported":
            api.save_composed_panel_dxf(
                _physical_panels(135.0), Path(stage) / "extra.dxf",
                pre_commit_guard=lambda: None,
            )
        if variant == "missing":
            return ["P2.dxf"], []
        if variant == "duplicate":
            return ["P1.dxf", "P1.dxf"], []
        if variant == "parent":
            return ["../P1.dxf"], []
        if variant == "unreported":
            return ["P1.dxf"], []
        assert variant == "exact"
        return ["P1.dxf"], []

    monkeypatch.setattr(gui, "_export_selected_parts", actual_engine)
    monkeypatch.setattr(
        gui.messagebox, "askyesno",
        lambda *_args, **_kwargs: events.append("overwrite") or True,
    )
    monkeypatch.setattr(
        gui.messagebox, "showerror",
        lambda _title, detail: events.append(("error", detail)),
    )
    monkeypatch.setattr(
        gui.messagebox, "showinfo",
        lambda _title, detail: events.append(("success", detail)),
    )
    gui.export_selected_dxf(host)
    return events


@pytest.mark.parametrize("variant", (
    "missing", "unreported", "duplicate", "parent",
))
def test_saved_gui_dxf_rejects_mismatched_stage_without_publish_or_overwrite(
    tmp_path, monkeypatch, variant,
):
    saved = _project_source(tmp_path)
    host, _workspace = _host(saved)
    existing = tmp_path / "P1.dxf"
    api.save_composed_panel_dxf(
        _physical_panels(110.0), existing,
        pre_commit_guard=lambda: None,
    )
    previous = existing.read_bytes()
    assert not ezdxf.readfile(existing).audit().errors

    events = _run_export(monkeypatch, host, tmp_path, variant=variant)
    assert any(
        isinstance(event, tuple) and event[0] == "error"
        and "暫存檔案與引擎回報不一致" in event[1]
        for event in events
    ), events
    assert not any(
        isinstance(event, tuple) and event[0] == "success"
        for event in events
    )
    assert "overwrite" not in events
    assert existing.read_bytes() == previous
    assert not (tmp_path / "P2.dxf").exists()
    assert not (tmp_path / "extra.dxf").exists()
    assert not ezdxf.readfile(existing).audit().errors


def test_saved_gui_dxf_matching_real_engine_stage_publishes_and_reopens(
    tmp_path, monkeypatch,
):
    saved = _project_source(tmp_path)
    host, _workspace = _host(saved)
    events = _run_export(monkeypatch, host, tmp_path, variant="exact")
    output = tmp_path / "P1.dxf"
    assert output.is_file()
    reopened = ezdxf.readfile(output)
    assert reopened.audit().errors == []
    assert any(x.dxf.layer == "CUTTING" for x in reopened.modelspace())
    assert any(
        isinstance(event, tuple) and event[0] == "success"
        for event in events
    ), events
    assert not any(
        isinstance(event, tuple) and event[0] == "error"
        for event in events
    )
