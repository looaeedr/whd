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
