"""#2517: independent EAR SIDE actions publish only their witnessed source.

Uses actual source-derived 3D contact/UV, Engine CUTTING+BEND+MARKING,
independent ezdxf reopen and the existing atomic two-side exporter.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project import export_actions as gui
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_issue1503_side_only_mfg_gui import _host
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


class Workspace:
    def __init__(self, source):
        self.source = deepcopy(source)

    def snapshot(self):
        return deepcopy(self.source)


def _export(mode, snapshot, geometry, folder, *, overwrite=False, guard=None):
    route = (
        api.export_receiving_ear_side_manufacturing_marking_dxf
        if mode == "mfg" else api.export_receiving_ear_side_check_only_dxf
    )
    return route(
        snapshot, geometry, folder,
        dimensions=(800.0, 1600.0, 350.0), sheet_thickness=2.0,
        overwrite=overwrite, pre_commit_guard=guard,
    )


@pytest.mark.parametrize("mode", ("mfg", "check"))
def test_real_gui_folder_edit_cannot_publish_stale_ear_side_dxf(
    tmp_path, monkeypatch, mode,
):
    snapshot, geometry = _actual(_assembled)
    original_source = deepcopy(snapshot)
    host, events = _host(snapshot, geometry)
    workspace = Workspace({"part_features": {"box_body:left_side": []}})
    host.fold_designer_app.designer_workspace = workspace

    def choose_folder(**_kwargs):
        events.append("folder")
        # The independent side buttons resolved true geometry before the
        # file dialog. Hole Editor source changes while the dialog is open.
        workspace.source["part_features"]["box_body:left_side"].append(
            {"confirmed": "new physical mark"}
        )
        return str(tmp_path)

    monkeypatch.setattr(gui.filedialog, "askdirectory", choose_folder)
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, detail: events.append(("error", detail)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda title, detail: events.append(("success", detail)))

    operator_action = (
        gui.export_receiving_ear_side_manufacturing_dxf
        if mode == "mfg" else gui.export_receiving_ear_side_check_dxf
    )
    assert operator_action(host) is None
    assert events[:3] == ["flush", "resolved", "folder"]
    assert any(isinstance(e, tuple) and e[0] == "error"
               and "DXF 工作區來源已變更" in e[1] for e in events)
    assert not any(isinstance(e, tuple) and e[0] == "success" for e in events)
    assert not list(tmp_path.glob("*.dxf"))
    assert snapshot == original_source


@pytest.mark.parametrize("mode", ("mfg", "check"))
def test_reopened_real_ear_side_exports_witness_source_five_times(
    tmp_path, mode,
):
    snapshot, geometry = _actual(_assembled)
    source_copy = json.loads(json.dumps(snapshot, ensure_ascii=False))
    assert source_copy == snapshot
    checks = []
    result = _export(
        mode, snapshot, geometry, tmp_path / mode,
        guard=lambda: checks.append("same source"),
    )
    assert len(checks) == 5
    assert len(result.output_paths) == 2
    assert snapshot == source_copy
    for _, filename in result.output_paths:
        entities = tuple(ezdxf.readfile(filename).modelspace())
        assert any(e.dxf.layer == "CUTTING" for e in entities)
        assert any(e.dxf.layer == "BEND" for e in entities)
        assert any(e.dxf.layer == "MARKING" for e in entities)
    assert result.whole_cabinet_manufacturing_ready is False if mode == "mfg" else (
        result.manufacturing_ready is False
    )


@pytest.mark.parametrize("mode", ("mfg", "check"))
def test_physical_source_drift_after_actual_pair_publish_rolls_back_both_sides(
    tmp_path, mode,
):
    snapshot, geometry = _actual(_assembled)
    before = deepcopy(snapshot)
    root = tmp_path / "retained"
    first = _export(mode, snapshot, geometry, root)
    retained = {path: Path(path).read_bytes() for _side, path in first.output_paths}
    checks = []

    def mutate_during_atomic_commit():
        checks.append("checked")
        if len(checks) == 5:
            snapshot["panel_name"] = "new operator panel"
        if snapshot != before:
            raise ValueError("EAR_SIDE_WORKSPACE_SOURCE_CHANGED")

    with pytest.raises(ValueError, match="EAR_SIDE_WORKSPACE_SOURCE_CHANGED"):
        _export(
            mode, snapshot, geometry, root, overwrite=True,
            guard=mutate_during_atomic_commit,
        )
    assert len(checks) == 5
    assert {p: Path(p).read_bytes() for p in retained} == retained
    assert {str(p) for p in root.glob("*.dxf")} == set(retained)
    assert not list(root.glob(".whd-dxf-backup-*"))
    assert not list(root.glob(".whd-ear-check-stage-*"))
    assert not list(root.glob(".whd-dxf-stage-*"))
    assert all(tuple(ezdxf.readfile(p).modelspace()) for p in retained)


@pytest.mark.parametrize("mode", ("mfg", "check"))
def test_invalid_supplied_guard_rejects_before_any_ear_side_dxf(
    tmp_path, mode,
):
    snapshot, geometry = _actual(_assembled)
    folder = tmp_path / "invalid"
    with pytest.raises(TypeError, match="WHD_PRECOMMIT_SOURCE_GUARD_INVALID"):
        _export(mode, snapshot, geometry, folder, guard="true")
    assert not folder.exists()

@pytest.mark.parametrize("mode", ("mfg", "check"))
def test_ear_gui_workspace_change_while_resolving_geometry_cannot_publish(
    tmp_path, monkeypatch, mode,
):
    snapshot, geometry = _actual(_assembled)
    host, events = _host(snapshot, geometry)
    workspace = Workspace({"part_features": {"box_body:left_side": []}})
    host.fold_designer_app.designer_workspace = workspace
    original_resolve = host.fold_designer_app._phase6_resolve_manufacturing_geometry

    def editing_resolver():
        # Geometry was requested from the old source but another editor
        # commits a Hole Editor change before its result is returned.
        workspace.source["part_features"]["box_body:left_side"].append(
            {"confirmed": "concurrent physical source"}
        )
        return original_resolve()

    host.fold_designer_app._phase6_resolve_manufacturing_geometry = editing_resolver
    monkeypatch.setattr(gui.filedialog, "askdirectory",
                        lambda **_kwargs: str(tmp_path))
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, detail: events.append(("error", detail)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda title, detail: events.append(("success", detail)))
    operator_action = (
        gui.export_receiving_ear_side_manufacturing_dxf
        if mode == "mfg" else gui.export_receiving_ear_side_check_dxf
    )
    assert operator_action(host) is None
    assert any(isinstance(e, tuple) and e[0] == "error"
               and "DXF 工作區來源已變更" in e[1] for e in events)
    assert not any(isinstance(e, tuple) and e[0] == "success" for e in events)
    assert not list(tmp_path.glob("*.dxf"))


@pytest.mark.parametrize("mode", ("mfg", "check"))
@pytest.mark.parametrize("changed", ("w", "t"))
def test_main_gui_unsaved_numeric_edit_in_side_dxf_dialog_fails_closed(
    tmp_path, monkeypatch, mode, changed,
):
    # Actual W800/T2 committed EAR contact + 2D side sheet source. Only the
    # main-GUI numeric reader is simulated; no Engine manufacturing API is
    # patched. A Tk edit can precede the next Fold Designer snapshot sync.
    snapshot, geometry = _actual(_assembled)
    saved = deepcopy(snapshot)
    host, events = _host(snapshot, geometry)
    live = {name: snapshot[name] for name in ("w", "h", "d", "t", "fw")}
    host.get_float_values = lambda: deepcopy(live)

    def choose_folder(**_kwargs):
        events.append("folder")
        live[changed] += 1.
        return str(tmp_path)

    monkeypatch.setattr(gui.filedialog, "askdirectory", choose_folder)
    monkeypatch.setattr(
        gui.messagebox, "showerror",
        lambda title, detail: events.append(("error", detail)),
    )
    monkeypatch.setattr(
        gui.messagebox, "showinfo",
        lambda title, detail: events.append(("success", detail)),
    )
    action = (gui.export_receiving_ear_side_manufacturing_dxf
              if mode == "mfg" else gui.export_receiving_ear_side_check_dxf)
    assert action(host) is None
    assert events[:3] == ["flush", "resolved", "folder"]
    assert any(isinstance(e, tuple) and e[0] == "error"
               and "DXF 即時操作來源已變更" in e[1] for e in events)
    assert not any(isinstance(e, tuple) and e[0] == "success" for e in events)
    assert not list(tmp_path.glob("*.dxf"))
    assert snapshot == saved


@pytest.mark.parametrize("mode", ("mfg", "check"))
def test_main_gui_unchanged_numeric_source_still_makes_actual_side_2d_3d_dxf(
    tmp_path, monkeypatch, mode,
):
    from ae_engine.assembly_geometry import build_joint_world_geometry
    from ae_engine.manufacturing_scene_access import owner_render_data

    snapshot, geometry = _actual(_assembled)
    host, events = _host(snapshot, geometry)
    live = {name: snapshot[name] for name in ("w", "h", "d", "t", "fw")}
    host.get_float_values = lambda: deepcopy(live)
    # Same 2D source handed into real Engine side manufacturing and actual
    # 3D world placement (source signed skin, not a GUI approximation).
    left = owner_render_data(geometry, "box_body:left_side")
    right = owner_render_data(geometry, "box_body:right_side")
    assert left is not None and right is not None
    world = build_joint_world_geometry(
        geometry.parts, (snapshot["w"], snapshot["h"], snapshot["d"]),
        snapshot["t"],
    )
    assert world["mapped_skin_triangles_by_part"]["box_body:left_side"]
    assert world["mapped_skin_triangles_by_part"]["box_body:right_side"]
    monkeypatch.setattr(gui.filedialog, "askdirectory",
                        lambda **_kwargs: str(tmp_path))
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, detail: events.append(("error", detail)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda title, detail: events.append(("success", detail)))
    action = (gui.export_receiving_ear_side_manufacturing_dxf
              if mode == "mfg" else gui.export_receiving_ear_side_check_dxf)
    result = action(host)
    assert result is not None, events
    assert len(result.output_paths) == 2
    assert not any(isinstance(e, tuple) and e[0] == "error" for e in events)
    assert [e[0] for e in events if isinstance(e, tuple)] == ["success"]
    for physical_side, filename in result.output_paths:
        assert physical_side in ("box_body:left_side", "box_body:right_side")
        reopened = ezdxf.readfile(filename)
        assert not reopened.audit().errors
        layers = {e.dxf.layer for e in reopened.modelspace()}
        assert {"CUTTING", "BEND", "MARKING"} <= layers
    if mode == "mfg":
        assert result.whole_cabinet_manufacturing_ready is False
    else:
        assert result.manufacturing_ready is False


def test_independent_ear_side_guard_notices_live_reader_attachment_after_dialog(
    tmp_path, monkeypatch,
):
    snapshot, geometry = _actual(_assembled)
    host, events = _host(snapshot, geometry)
    assert not hasattr(host, "get_float_values")

    def directory(**_kwargs):
        host.get_float_values = lambda: {
            k: snapshot[k] for k in ("w", "h", "d", "t")
        }
        return str(tmp_path)

    monkeypatch.setattr(gui.filedialog, "askdirectory", directory)
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda title, detail: events.append(("error", detail)))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda title, detail: events.append(("success", detail)))
    assert gui.export_receiving_ear_side_check_dxf(host) is None
    assert any(isinstance(e, tuple) and e[0] == "error"
               and "DXF 即時操作來源已變更" in e[1] for e in events)
    assert not list(tmp_path.glob("*.dxf"))
