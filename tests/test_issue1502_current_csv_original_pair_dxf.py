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
        snap, assembly_parts=parts, base_spec=(
            _spec(snap) if snap.get("nfb_config_submitted") is True else None
        ),
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
    # Today's committed Flat source has its original one perimeter +
    # four EAR slots, plus source-verified PAD square locator CUTTING.
    # Compare every saved polygon to the ACTUAL resolved FinalScene, rather
    # than hardcoding the pre-PAD count of five or trusting metadata alone.
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    physical_base = next(p.render_data for p in parts if p.part_key == "base_plate")
    source_cutting = [
        p for p in physical_base.scene.primitives
        if isinstance(p, PolylinePrimitive) and p.closed and p.layer == "CUTTING"
    ]
    saved_cutting = [
        p for p in b if p.dxftype() == "LWPOLYLINE"
        and p.closed and p.dxf.layer == "CUTTING"
    ]
    pad_owners = tuple(physical_base.metadata["nfb_v5_pad_square_owners"])
    assert pad_owners and sum(count for _, count in pad_owners) == 4
    assert len(source_cutting) == len(saved_cutting) == 5 + sum(
        count for _, count in pad_owners
    )
    def source_vertices(poly):
        return tuple((round(float(p.x), 5), round(float(p.y), 5)) for p in poly.points)
    def saved_vertices(poly):
        return tuple((round(float(x), 5), round(float(y), 5))
                     for x, y in poly.get_points("xy"))
    assert sorted(map(source_vertices, source_cutting)) == sorted(
        map(saved_vertices, saved_cutting)
    )
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
    with pytest.raises(ValueError, match="identity drift|IDENTITY_DRIFT|RECEIVING_FLAT_NFB_BAY_SCOPE_DRIFT"):
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
    cleared.pop("nfb_config", None)
    # The original #1502 test uses a minimal Set/Bay manufacturing fixture
    # (no ReceivingLayout schema), not a persisted normalized layout. Restore
    # its selected Bay authority directly; only a genuinely unconfigured Bay
    # may use the original legacy no-NFB path.
    bay = cleared["receiving_layout"]["sets"][0]["bays"][0]
    assert bay["nfb_config_submitted"] is True
    bay["nfb_config_submitted"] = False
    bay.pop("nfb_config", None)
    assert "nfb_config" not in bay
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


def test_original_operator_left_two_source_equivalent_models_roundtrip(tmp_path):
    # The user's LEFT original has TWO 44x194 / Ø5.1 quartets on ONE
    # physical base. Different numeric catalog names with exactly the
    # same source geometry must traverse the ordinary two-sheet operator
    # export, not just the physical configuration resolver.
    snap = _current(model_second="3P400SN")
    from ae_engine.receiving_base_plate_config import (
        receiving_base_plate_values, receiving_base_plate_blank_dimensions,
    )
    assert receiving_base_plate_values(snap)["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert receiving_base_plate_blank_dimensions(snap) == (710., 300.)
    parts = _scene(snap)
    receipt = _export(snap, parts, tmp_path)
    assert receipt.source_hole_ids == ("nfb:0", "nfb:1")
    assert len(receipt.check_q_key) == 64
    paths = (Path(receipt.inner_door_path), Path(receipt.base_plate_path))
    assert all(path.is_file() for path in paths)
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    base = ezdxf.readfile(paths[1]).modelspace()
    screws = [item for item in base
              if item.dxftype() == "CIRCLE" and item.dxf.layer == "CUTTING"]
    slots = [item for item in base
             if item.dxftype() == "LWPOLYLINE" and item.closed
             and item.dxf.layer == "CUTTING"]
    assert len(screws) == 8
    assert all(abs(float(h.dxf.radius) - 2.55) < 1e-6 for h in screws)
    assert len(slots) == 5  # one blank + four original EAR fixing slots
    assert sum(1 for h in base if h.dxf.layer == "BEND") == 2
    door = ezdxf.readfile(paths[0]).modelspace()
    openings = [item for item in door
                if item.dxftype() == "LWPOLYLINE" and item.closed
                and item.dxf.layer == "CUTTING"]
    assert len(openings) >= 3  # actual inner-door perimeter + both NFB openings


def test_three_same_tier_400_switches_share_one_source_base_and_reopen_dxf(tmp_path):
    # One submitted vertical tier can have 3 horizontally arranged NFBs.
    # The NFBConfig owns all 3 X locations; source LEFT still owns one
    # cabinet-centred base and its original four ear-mount slots.
    snap = _current(model_second="3P400SN")
    holes = snap["nfb_config"]["holes"]
    holes[0]["manual_x_mm"] = -180.
    holes[1]["manual_x_mm"] = 0.
    third = deepcopy(holes[0])
    third.update(physical_hole_id="nfb:third", slot_index=2,
                 manual_x_mm=180., model_filename="nfbv5:士林:2P400")
    holes.append(third)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    parts = _scene(snap)
    receipt = _export(snap, parts, tmp_path)
    assert receipt.source_hole_ids == ("nfb:0", "nfb:1", "nfb:third")
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    base = ezdxf.readfile(receipt.base_plate_path).modelspace()
    circles = [p for p in base if p.dxftype() == "CIRCLE"
               and p.dxf.layer == "CUTTING"]
    assert len(circles) == 12
    assert all(abs(float(p.dxf.radius) - 2.55) < 1e-6 for p in circles)
    assert len([p for p in base if p.dxftype() == "LWPOLYLINE"
                and p.closed and p.dxf.layer == "CUTTING"]) == 5
    assert sum(1 for p in base if p.dxf.layer == "BEND") == 2
    door = ezdxf.readfile(receipt.inner_door_path).modelspace()
    assert len([p for p in door if p.dxftype() == "LWPOLYLINE"
                and p.closed and p.dxf.layer == "CUTTING"]) >= 4


def test_normal_operator_export_single_125_current_csv_uses_real_flat_source(tmp_path):
    snap = _current()
    only = deepcopy(snap["nfb_config"]["holes"][1])
    only.update(slot_index=0, layer_index=0, manual_x_mm=0.)
    snap["nfb_config"]["holes"] = [only]
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    parts = _scene(snap)
    receipt = _export(snap, parts, tmp_path)
    assert receipt.source_hole_ids == ("nfb:1",)
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    plate = ezdxf.readfile(receipt.base_plate_path).modelspace()
    holes = [x for x in plate if x.dxftype() == "CIRCLE"
             and x.dxf.layer == "CUTTING"]
    assert len(holes) == 4
    assert all(abs(float(x.dxf.radius) - 1.6) < 1e-6 for x in holes)
    assert len([x for x in plate if x.dxftype() == "LWPOLYLINE"
                and x.closed and x.dxf.layer == "CUTTING"]) == 5
    assert sum(1 for x in plate if x.dxf.layer == "BEND") == 2


def test_original_operator_does_not_equate_two_brands_on_one_flat_base(tmp_path):
    snap = _current(model_second="3P400SN")
    row = snap["nfb_config"]["holes"][1]
    row.update(model_filename="nfbv5:伍菱:3P400SN", source_brand="伍菱")
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    assert receiving_base_plate_values(snap)["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    receipt = _export(snap, _scene(snap), tmp_path)
    assert receipt.source_hole_ids == ("nfb:0", "nfb:1")
    plate = ezdxf.readfile(receipt.base_plate_path).modelspace()
    assert sum(1 for x in plate if x.dxftype() == "CIRCLE"
               and x.dxf.layer == "CUTTING") == 8
    door = ezdxf.readfile(receipt.inner_door_path).modelspace()
    assert sum(1 for x in door if x.dxftype() == "LWPOLYLINE"
               and x.closed and x.dxf.layer == "CUTTING") >= 3
