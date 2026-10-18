# -*- coding: utf-8 -*-
"""#1503 source SIDE MFG operator action, with actual DXF writer and Tk button."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from gui_modules.project import export_actions
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _host(snapshot, geometry):
    events = []
    class Designer:
        _phase6_input_snapshot = snapshot
        def _phase6_resolve_manufacturing_geometry(self):
            events.append("resolved")
            return geometry
    host = SimpleNamespace(
        fold_designer_app=Designer(),
        _flush_phase6_authoritative_state=lambda: events.append("flush"),
    )
    return host, events


def _messages(monkeypatch, directory, events):
    monkeypatch.setattr(export_actions.filedialog, "askdirectory",
                        lambda **kw: events.append("folder") or str(directory))
    monkeypatch.setattr(export_actions.messagebox, "showinfo",
                        lambda title, message: events.append(("success", title, message)))
    monkeypatch.setattr(export_actions.messagebox, "showerror",
                        lambda title, message: events.append(("error", title, message)))


def test_real_gui_action_outputs_true_source_verified_standard_side_dxf(
    tmp_path, monkeypatch,
):
    snap,geom=_actual(_assembled)
    host,events=_host(snap,geom)
    _messages(monkeypatch,tmp_path,events)
    result=export_actions.export_receiving_ear_side_manufacturing_dxf(host)
    assert result is not None
    assert result.status == "EAR_SIDE_ONLY_MFG_MARKING_VERIFIED"
    assert result.side_only_manufacturing_marking_verified
    assert not result.whole_cabinet_manufacturing_ready
    assert not result.welding_workmanship_certified
    assert events[:3] == ["flush","resolved","folder"]
    success=[x for x in events if isinstance(x,tuple) and x[0]=="success"]
    assert len(success)==1
    assert "僅側板" in success[0][1]
    assert "整箱" in success[0][2]
    assert {p.name for p in tmp_path.glob("*.dxf")} == {
        "box_body__left_side.dxf", "box_body__right_side.dxf",
    }


@pytest.mark.parametrize("updates", (
    {"model":"金庫型"}, {"nfb_config_submitted":False},
    {"active_mode":"quantity"}, {"w":750.}, {"t":3.},
))
def test_invalid_gui_input_rejected_before_resolving_or_asking_folder(
    tmp_path, monkeypatch, updates,
):
    snap,geom=_actual(_assembled)
    invalid={**snap,**updates}
    host,events=_host(invalid,geom)
    _messages(monkeypatch,tmp_path,events)
    assert export_actions.export_receiving_ear_side_manufacturing_dxf(host) is None
    assert events[0]=="flush"
    assert not any(e=="resolved" or e=="folder" for e in events)
    assert events[-1][0]=="error"
    assert not list(tmp_path.glob("*"))


def test_real_primary_tk_mounts_both_independent_actions_and_routes_mfg(
    monkeypatch,
):
    import tkinter as tk
    import gui
    called=[]
    monkeypatch.setattr(
        gui.Phase6PrimaryApplication,
        "export_receiving_ear_side_manufacturing_dxf",
        lambda app: called.append(app),
    )
    root=tk.Tk()
    try:
        root.geometry("1400x900+20+20")
        app=gui.Phase6PrimaryApplication(root)
        root.update()
        assert app._legacy_2d_compat_host is None
        check=app.btn_ear_side_check_dxf
        mfg=app.btn_ear_side_mfg_dxf
        assert check.winfo_viewable() and mfg.winfo_viewable()
        assert check.master is mfg.master
        assert "CHECK" in check.cget("text")
        assert "正式 MARKING" in mfg.cget("text")
        assert mfg.winfo_rootx()>=root.winfo_rootx()
        assert mfg.winfo_rootx()+mfg.winfo_width()<=root.winfo_rootx()+root.winfo_width()
        mfg.invoke()
        assert called==[app]
    finally:
        root.destroy()
