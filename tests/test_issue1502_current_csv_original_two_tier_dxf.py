# -*- coding: utf-8 -*-
"""#1502: same existing GUI DXF action handles BOTH real NFB tiers, not a new button."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.manufacturing_api import build_inner_door_panel_render_data
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from ae_engine.receiving_nfb_layer_physical_parts import (
    expand_receiving_nfb_layer_parts,
)
from gui_modules.application.receiving_nfb_pair_partial_export_action import (
    export_current_csv_nfb_door_base_pair,
)
from phase6_final_scene_contracts import AssemblyScenePart
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source


def _current_two_tiers():
    snap = _two_tier()
    for index, row in enumerate(snap["nfb_config"]["holes"]):
        row.update(
            model_filename=("nfbv5:士林:2P400", "nfbv5:士林:3P125SN")[index],
            source_brand="士林", manual_x_state="CONFIRMED",
            manual_x_mm=(-100. if index == 0 else 100.),
            datum_revision="CURRENT_CSV_X",
            datum_snapshot={"w": 800., "inner_door": "upper"},
        )
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    return snap


def _actual_scene(snap):
    panel = next(p for p in derive_inner_door_panels(snap)
                 if str(p.cell_key).split(":")[-1] == "0")
    physical_door = AssemblyScenePart(
        part_key=panel.stable_id,
        render_data=build_inner_door_panel_render_data(panel),
        x_profile=(), y_profile=(), placement="offset",
        offset=(0., 0., 0.),
    )
    blanks = expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    return apply_committed_csv_v5_to_canonical_parts(
        snap, (physical_door,) + blanks,
    )


def _save(snap, parts, folder):
    return export_current_csv_nfb_door_base_pair(
        snap, assembly_parts=parts, base_spec=None, output_directory=folder,
    )


def test_existing_operator_export_writes_one_door_and_two_real_bases(tmp_path):
    snap = _current_two_tiers()
    parts = _actual_scene(snap)
    receipt = _save(snap, parts, tmp_path)
    paths = (receipt.inner_door_path,) + receipt.base_plate_paths
    assert len(paths) == 3 and len(set(paths)) == 3
    assert all(Path(v).is_file() for v in paths)
    assert len(list(tmp_path.glob("*.dxf"))) == 3
    assert receipt.source_hole_ids == ("tier:0:switch", "tier:1:switch")
    assert receipt.scope == "CSV_TWO_TIER_PART_ONLY_NOT_WHOLE_CABINET"
    assert len(receipt.check_q_keys) == 2
    assert all(len(key) == 64 for key in receipt.check_q_keys)
    for path in receipt.base_plate_paths:
        msp = ezdxf.readfile(path).modelspace()
        assert len([p for p in msp if p.dxftype() == "CIRCLE"
                    and p.dxf.layer == "CUTTING"]) == 4
        assert len([p for p in msp if p.dxftype() == "LWPOLYLINE"
                    and p.closed and p.dxf.layer == "CUTTING"]) == 5
        assert any(p.dxf.layer == "BEND" for p in msp)
    assert len([p for p in ezdxf.readfile(receipt.inner_door_path).modelspace()
                if p.dxftype() == "LWPOLYLINE"
                and p.closed and p.dxf.layer == "CUTTING"]) >= 3


def test_wrong_layer_or_missing_actual_plate_produces_no_partial_dxf(tmp_path):
    snap = _current_two_tiers()
    parts = _actual_scene(snap)
    with pytest.raises(ValueError, match="MISSING_INSTALLED_PHYSICAL_PART"):
        _save(snap, parts[:2], tmp_path)
    changed = replace(parts[2], offset=(
        parts[2].offset[0], parts[2].offset[1], parts[2].offset[2]+2.,
    ))
    with pytest.raises(ValueError, match="INSTALL_XYZ_MISMATCH"):
        _save(snap, parts[:2] + (changed,), tmp_path)
    corrupted = replace(parts[2], render_data=replace(
        parts[2].render_data,
        metadata={**parts[2].render_data.metadata, "stable_id":"wrong"},
    ))
    with pytest.raises(ValueError, match="FINALSCENE_DIFFERS_FROM_CSV"):
        _save(snap, parts[:2] + (corrupted,), tmp_path)
    assert not list(tmp_path.glob("*.dxf"))


def test_changed_csv_x_does_not_reuse_previous_view_or_overwrite_dxf(tmp_path):
    snap = _current_two_tiers()
    actual = _actual_scene(snap)
    changed = deepcopy(snap)
    changed["nfb_config"]["holes"][1]["manual_x_mm"] += 25.
    changed["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        changed["nfb_config"]
    )
    with pytest.raises(ValueError, match="FINALSCENE_DIFFERS_FROM_CSV"):
        _save(changed, actual, tmp_path)
    assert not list(tmp_path.glob("*.dxf"))
    good = _save(snap, actual, tmp_path)
    previous = tuple(Path(path).read_bytes()
                     for path in (good.inner_door_path, *good.base_plate_paths))
    with pytest.raises(FileExistsError, match="EXISTING_DXF"):
        _save(snap, actual, tmp_path)
    assert previous == tuple(Path(path).read_bytes()
                             for path in (good.inner_door_path, *good.base_plate_paths))


def test_all_three_dxf_reopens_are_required_before_any_commit(monkeypatch, tmp_path):
    import gui_modules.application.receiving_nfb_pair_partial_export_action as action
    import ae_engine.manufacturing_verification as verification
    snap = _current_two_tiers()
    scene = _actual_scene(snap)
    actual = verification.verify_saved_part_render_data_dxf
    calls = {"n":0}
    def reject_last(*args):
        calls["n"] += 1
        if calls["n"] == 3:
            return type("Receipt", (), {"ok":False})()
        return actual(*args)
    # Action previously imported a verification alias into its module scope;
    # tier export deliberately imports within the function. Inject that
    # same canonical verification owner via the dependency module.
    monkeypatch.setattr(verification, "verify_saved_part_render_data_dxf", reject_last)
    with pytest.raises(ValueError, match="DXF_ROUNDTRIP_FAILED"):
        _save(snap, scene, tmp_path)
    assert calls["n"] == 3
    assert not list(tmp_path.glob("*.dxf"))


def test_original_operator_action_is_shared_for_one_or_two_tiers():
    import inspect
    from gui_modules.application import (
        fold_designer_composition_receiving, receiving_multi_settings_window,
    )
    gui = inspect.getsource(fold_designer_composition_receiving)
    modal = inspect.getsource(receiving_multi_settings_window)
    assert 'count == 2' in gui
    assert 'current_csv_pair_source(set_index, bay_index)' in gui
    assert 'export_current_csv_nfb_door_base_pair(' in gui
    assert 'text="輸出內門＋底板 DXF（成對部分）"' in modal
    assert "輸出 CSV 底板 DXF（單片）" not in modal


def test_three_same_tier_400_switches_and_one_second_tier_reopen_three_dxfs(tmp_path):
    snap = _current_two_tiers()
    holes = snap["nfb_config"]["holes"]
    holes[0]["manual_x_mm"] = -180.
    holes[1]["model_filename"] = "nfbv5:士林:2P400"
    for slot, x in ((1, 0.), (2, 180.)):
        extra = deepcopy(holes[0])
        extra.update(physical_hole_id=f"tier:0:extra:{slot}",
                     slot_index=slot, manual_x_mm=x,
                     model_filename="nfbv5:士林:2P400")
        holes.append(extra)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    parts = _actual_scene(snap)
    receipt = _save(snap, parts, tmp_path)
    assert len(receipt.base_plate_paths) == 2
    assert len(list(tmp_path.glob("*.dxf"))) == 3
    counts = []
    for path in receipt.base_plate_paths:
        base = ezdxf.readfile(path).modelspace()
        counts.append(sum(1 for p in base if p.dxftype() == "CIRCLE"
                          and p.dxf.layer == "CUTTING"))
        assert sum(1 for p in base if p.dxftype() == "LWPOLYLINE"
                   and p.closed and p.dxf.layer == "CUTTING") == 5
    assert sorted(counts) == [4, 12]
    assert len(receipt.check_q_keys) == 2
    assert len(receipt.source_hole_ids) == 4
