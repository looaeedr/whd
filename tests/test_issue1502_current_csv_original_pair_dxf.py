# -*- coding: utf-8 -*-
"""#1502 original Receiving DXF control consumes one canonical NFB CSV source."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.manufacturing_api import build_inner_door_panel_render_data
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from phase6_final_scene_contracts import AssemblyScenePart
from gui_modules.application.receiving_nfb_pair_partial_export_action import (
    export_current_csv_nfb_door_base_pair,
)
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
from tests.test_issue1502_source_derived_center_base import _spec


def _scene(snapshot):
    panel = next(p for p in derive_inner_door_panels(snapshot)
                 if str(p.cell_key).split(":")[-1] == "0")
    actual = AssemblyScenePart(
        part_key=panel.stable_id,
        render_data=build_inner_door_panel_render_data(panel),
        x_profile=(), y_profile=(), placement="offset",
        offset=(0., 0., 0.),
    )
    return apply_committed_csv_v5_to_canonical_parts(
        snapshot, (actual, _make(snapshot)),
    )


def _export(snap, parts, root):
    return export_current_csv_nfb_door_base_pair(
        snap, assembly_parts=parts, base_spec=_spec(snap),
        output_directory=root,
    )


def test_normal_existing_pair_export_writes_two_verified_actual_csv_dxfs(tmp_path):
    snapshot = _current()
    assert "receiving_base_plate" not in snapshot
    parts = _scene(snapshot)
    actual = _export(snapshot, parts, tmp_path)
    assert actual.source_hole_ids == ("nfb:0", "nfb:1")
    assert len(actual.check_q_key) == 64
    door = Path(actual.inner_door_path)
    base = Path(actual.base_plate_path)
    assert door.is_file() and base.is_file() and door != base
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    a = ezdxf.readfile(door).modelspace()
    b = ezdxf.readfile(base).modelspace()
    assert len([p for p in a if p.dxftype()=="LWPOLYLINE"
                and p.closed and p.dxf.layer=="CUTTING"]) >= 2
    assert len([p for p in b if p.dxftype()=="CIRCLE"
                and p.dxf.layer=="CUTTING"]) == 8
    assert len([p for p in b if p.dxftype()=="LWPOLYLINE"
                and p.closed and p.dxf.layer=="CUTTING"]) == 5
    assert any(p.dxf.layer=="BEND" for p in b)


def test_stale_scene_or_wrong_bay_cannot_export_to_existing_operator_action(tmp_path):
    snapshot = _current()
    parts = _scene(snapshot)
    wrong = replace(parts[1], render_data=replace(parts[1].render_data,
        metadata={**parts[1].render_data.metadata, "stable_id": "wrong"}))
    with pytest.raises(ValueError, match="CURRENT_FINALSCENE"):
        _export(snapshot, (parts[0], wrong), tmp_path)
    stale = deepcopy(snapshot)
    stale["nfb_config"]["holes"][1]["manual_x_mm"] += 20.
    stale["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        stale["nfb_config"]
    )
    with pytest.raises(ValueError, match="CURRENT_FINALSCENE"):
        _export(stale, parts, tmp_path)
    wrong_bay = deepcopy(snapshot)
    wrong_bay["_receiving_runtime_selection"]["bay_id"] = "different"
    with pytest.raises(ValueError, match="IDENTITY_DRIFT"):
        _export(wrong_bay, parts, tmp_path)
    assert not list(tmp_path.glob("*.dxf"))


def test_pair_export_rejects_unsubmitted_and_refuses_silent_overwrite(tmp_path):
    snapshot = _current()
    parts = _scene(snapshot)
    first = _export(snapshot, parts, tmp_path)
    first_bytes = Path(first.inner_door_path).read_bytes()
    with pytest.raises(FileExistsError, match="EXISTING_DXF"):
        _export(snapshot, parts, tmp_path)
    assert Path(first.inner_door_path).read_bytes() == first_bytes
    cleared = deepcopy(snapshot)
    cleared["nfb_config_submitted"] = False
    with pytest.raises(ValueError, match="SOURCE_UNAVAILABLE"):
        _export(cleared, parts, tmp_path)


def test_dxf_roundtrip_failure_never_partially_publishes(monkeypatch,tmp_path):
    import gui_modules.application.receiving_nfb_pair_partial_export_action as action
    import ae_engine.manufacturing_verification as verification

    snap = _current()
    parts = _scene(snap)
    call_count = {"n": 0}
    real = verification.verify_saved_part_render_data_dxf
    def fail_second(render, path):
        call_count["n"] += 1
        if call_count["n"] == 2:
            return SimpleNamespace(ok=False)
        return real(render,path)
    monkeypatch.setattr(verification,"verify_saved_part_render_data_dxf",fail_second)
    with pytest.raises(ValueError,match="ROUNDTRIP_FAILED"):
        _export(snap, parts, tmp_path)
    assert not list(tmp_path.glob("*.dxf"))


def test_original_gui_pair_port_auto_consumes_csv_without_extra_button():
    import inspect
    from gui_modules.application import (
        fold_designer_composition_receiving, receiving_multi_settings_window,
    )
    gui=inspect.getsource(fold_designer_composition_receiving)
    modal=inspect.getsource(receiving_multi_settings_window)
    assert "current_csv_pair_source(set_index, bay_index)" in gui
    assert "export_current_csv_nfb_door_base_pair(" in gui
    assert '"pair_partial_export": export_partial_nfb_door_base_pair' in gui
    assert 'text="輸出內門＋底板 DXF（成對部分）"' in modal
    assert "輸出 CSV 底板 DXF（單片）" not in modal
