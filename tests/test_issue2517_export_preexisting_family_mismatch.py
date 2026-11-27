"""#2517: original GUI Family must match saved Engine Family before DXF staging.

Uses the already verified real .p6fold, genuine Engine CUTTING/BEND DXF and
Receiving EAR signed-geometry fixtures; no manufactured geometry is mocked.
"""
from copy import deepcopy
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project import export_actions as gui
from tests.test_issue2517_gui_final_dxf_publish_source_guard import (
    _host as _selected_host,
    _physical_panels,
    _project_source,
    _run_real_gui_export,
)
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_issue1503_side_only_mfg_gui import _host as _ear_host
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def test_selected_dxf_preexisting_unsynced_family_preserves_previous_real_dxf(
    tmp_path, monkeypatch,
):
    saved = _project_source(tmp_path)
    before = deepcopy(saved)
    host, workspace = _selected_host(saved)
    # The operator had already switched to Receiving *before* export starts,
    # while saved Vault 2D/3D/PartSpec still describes the previous Family.
    host.baseline_var = SimpleNamespace(get=lambda: "受電箱")
    target = tmp_path / "P1.dxf"
    api.save_composed_panel_dxf(
        _physical_panels(110.0), target, pre_commit_guard=lambda: None,
    )
    original = target.read_bytes()

    events = _run_real_gui_export(monkeypatch, host, tmp_path)

    assert any(
        isinstance(event, tuple) and event[0] == "error"
        and "DXF 即時箱型與製造快照不一致" in event[1]
        for event in events
    )
    assert not any(isinstance(event, tuple) and event[0] == "success"
                   for event in events)
    assert target.read_bytes() == original
    reopened = ezdxf.readfile(target)
    assert not reopened.audit().errors
    assert {"CUTTING", "BEND"} <= {e.dxf.layer for e in reopened.modelspace()}
    assert host.fold_designer_app._phase6_input_snapshot == before
    assert workspace.snapshot()["part_features"] == saved["part_features"]


@pytest.mark.parametrize("mode", ("mfg", "check"))
def test_ear_side_preexisting_unsynced_family_rejects_before_3d_and_dxf(
    tmp_path, monkeypatch, mode,
):
    saved, geometry = _actual(_assembled)
    before = deepcopy(saved)
    host, events = _ear_host(saved, geometry)
    # Real Receiving EAR signed world geometry exists, but the GUI operator
    # has already selected Vault before this button starts.
    assert geometry.part("box_body") is not None
    host.baseline_var = SimpleNamespace(get=lambda: "金庫型")
    host.get_float_values = lambda: deepcopy({
        name: saved[name] for name in ("w", "h", "d", "t", "fw")
    })
    monkeypatch.setattr(
        gui.filedialog, "askdirectory",
        lambda **_kwargs: events.append("folder") or str(tmp_path),
    )
    monkeypatch.setattr(
        gui.messagebox, "showerror",
        lambda _title, detail: events.append(("error", detail)),
    )
    monkeypatch.setattr(
        gui.messagebox, "showinfo",
        lambda _title, detail: events.append(("success", detail)),
    )
    action = (gui.export_receiving_ear_side_manufacturing_dxf
              if mode == "mfg" else gui.export_receiving_ear_side_check_dxf)

    assert action(host) is None
    assert events[0] == "flush"
    assert "resolved" not in events
    assert "folder" not in events
    assert any(
        isinstance(event, tuple) and event[0] == "error"
        and "DXF 即時箱型與製造快照不一致" in event[1]
        for event in events
    )
    assert not any(isinstance(event, tuple) and event[0] == "success"
                   for event in events)
    assert not tuple(tmp_path.glob("*.dxf"))
    assert saved == before


def test_same_original_family_model_alias_still_uses_public_engine_gate():
    snapshot = {"model": "金庫型", "t": 2.0}
    designer = SimpleNamespace(_phase6_input_snapshot=deepcopy(snapshot))
    live = {
        "model_selection": {"reader_present": True, "value": "金庫型"},
    }
    guard = gui._current_authoritative_export_guard(
        designer, snapshot, operator_source=live,
        operator_source_reader=lambda: deepcopy(live),
    )
    guard()
    assert api.operator_resolve_legacy_baseline_manufacturing_family(
        live["model_selection"]["value"]
    ) == "金庫型"


@pytest.mark.parametrize("model", ("受電箱", "", None, True))
def test_direct_engine_export_family_gate_rejects_conflicting_present_selector(model):
    saved = {"model": "金庫型"}
    live = {"model_selection": {"reader_present": True, "value": model}}
    with pytest.raises(ValueError, match="DXF 即時箱型與製造快照不一致"):
        api.require_selected_export_matching_operator_family(saved, live)


def test_direct_engine_export_gate_preserves_family_alias_and_absent_reader():
    saved = {"cabinet_type": "金庫型"}
    api.require_selected_export_matching_operator_family(
        saved, {"model_selection": {"reader_present": True, "value": "VAULT"}},
    )
    api.require_selected_export_matching_operator_family(
        saved, {"model_selection": {"reader_present": False, "value": "受電箱"}},
    )


def test_native_selected_dxf_publishes_matching_family_and_preserves_dxf_on_conflict(
    tmp_path, monkeypatch,
):
    import os
    from pathlib import Path
    import tkinter as tk
    from gui import Phase6PrimaryApplication

    if os.name != "nt" and not os.environ.get("DISPLAY"):
        pytest.skip("actual Tk requires a desktop display")

    root = tk.Tk()
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        fixture = (
            Path(__file__).parent / "fixtures" / "vault_overlay_w400_t2_fw25.p6fold"
        )
        monkeypatch.setattr(gui.filedialog, "askopenfilename", lambda **kw: str(fixture))
        app.project_file_menu.invoke(0)
        root.update()
        assert host.project_controller.project_path == str(fixture)
        assert host.baseline_var.get() == app._phase6_input_snapshot["model"] == "金庫型"
        for key in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
            getattr(host, f"export_{key}_var").set(key == "door")

        folders, errors, successes = [], [], []
        monkeypatch.setattr(
            gui.filedialog, "askdirectory",
            lambda **kw: folders.append(tmp_path) or str(tmp_path),
        )
        monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kw: errors.append(args))
        monkeypatch.setattr(gui.messagebox, "showwarning", lambda *args, **kw: errors.append(args))
        monkeypatch.setattr(gui.messagebox, "showinfo", lambda *args, **kw: successes.append(args))

        gui.export_selected_dxf(host)
        assert not errors and len(successes) == len(folders) == 1
        target, = tmp_path.glob("*.dxf")
        before = target.read_bytes()
        doc = ezdxf.readfile(target)
        assert doc.header["$INSUNITS"] == 4 and not doc.audit().errors
        assert {"CUTTING", "BEND"} <= {e.dxf.layer for e in doc.modelspace()}

        # Model a not-yet-synced selector using a real Tk control, leaving the
        # authentic Designer, project, resolution and export path unchanged.
        matching_selector = host.baseline_var
        host.baseline_var = tk.StringVar(root, "受電箱")
        try:
            gui.export_selected_dxf(host)
        finally:
            host.baseline_var = matching_selector
        assert len(errors) == len(successes) == len(folders) == 1
        assert "DXF 即時箱型與製造快照不一致" in errors[0][1]
        assert tuple(tmp_path.glob("*.dxf")) == (target,)
        assert target.read_bytes() == before
    finally:
        root.destroy()
