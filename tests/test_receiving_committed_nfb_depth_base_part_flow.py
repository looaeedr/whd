# -*- coding: utf-8 -*-
"""#1502: live submitted Bay → Set brand CSV → original BasePlatePartSpec."""
from copy import deepcopy
from types import SimpleNamespace
import pytest

from ae_engine.receiving_base_plate_config import (
    receiving_base_plate_blank_dimensions,
    receiving_base_plate_values,
)
from ae_engine.receiving_nfb_depth_surface_policy import (
    committed_receiving_nfb_depth_pair_mm,
)


def _snapshot(brand="士林", shallow="125_90X155_72.dxf"):
    config = {
        "layer_count": 1,
        "holes": [
            {"physical_hole_id": "nfb:1", "model_filename": "400_140X257_107.dxf",
             "slot_index": 0},
            {"physical_hole_id": "nfb:2", "model_filename": shallow,
             "slot_index": 1},
        ],
    }
    return {
        "model": "受電箱", "w": 800., "h": 1600., "d": 350., "t": 2.,
        "receiving_base_plate": {
            "pattern": "CENTER_DOUBLE_SIDE_FOLD", "height": 350.,
            "shrink_top": 55., "shrink_bottom": 55.,
            "shrink_left": 85., "shrink_right": 85., "bend": 20.,
        },
        "receiving_layout": {"sets": [{
            "stable_id": "setA", "switch_brand": brand,
            "bays": [{"stable_id": "bayA", "nfb_config_submitted": True,
                      "nfb_config": deepcopy(config)}],
        }]},
        "_receiving_runtime_selection": {
            "set_index": 0, "bay_index": 0,
            "set_id": "setA", "bay_id": "bayA",
        },
        "nfb_config_submitted": True, "nfb_config": config,
    }


def test_shihlin_saved_one_row_two_models_reaches_existing_base_blank_and_values():
    snap = _snapshot()
    assert committed_receiving_nfb_depth_pair_mm(snap) == (107., 72.)
    values = receiving_base_plate_values(snap)
    assert values["receiving_nfb_depth_pair_mm"] == (107., 72.)
    assert receiving_base_plate_blank_dimensions(snap) == (772., 240.)


def test_source_csv_not_magic_33_alternate_model_reaches_real_blank():
    snap = _snapshot(shallow="100_75X130_68.dxf")
    assert committed_receiving_nfb_depth_pair_mm(snap) == (107., 68.)
    values = receiving_base_plate_values(snap)
    assert values["receiving_nfb_depth_pair_mm"] == (107., 68.)
    # 107-68-T2=37; W630+2*(40+37-2)=780
    assert receiving_base_plate_blank_dimensions(snap) == (780., 240.)


def test_unsubmitted_or_same_model_retains_old_nonmanufacturing_preview():
    snap = _snapshot()
    snap["nfb_config_submitted"] = False
    assert committed_receiving_nfb_depth_pair_mm(snap) is None
    assert receiving_base_plate_values(snap)["receiving_nfb_depth_pair_mm"] is None
    assert receiving_base_plate_blank_dimensions(snap) == (772., 240.)
    snap = _snapshot()
    snap["nfb_config"]["holes"][1]["model_filename"] = snap["nfb_config"]["holes"][0]["model_filename"]
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    assert committed_receiving_nfb_depth_pair_mm(snap) is None


def test_same_set_different_bay_or_brand_drift_cannot_reinterpret_old_model():
    snap = _snapshot()
    snap["_receiving_runtime_selection"]["bay_id"] = "other-bay"
    with pytest.raises(ValueError, match="identity drift"):
        committed_receiving_nfb_depth_pair_mm(snap)
    snap = _snapshot()
    snap["receiving_layout"]["sets"][0]["switch_brand"] = "東元"
    with pytest.raises(ValueError, match="unknown|source|depth|model|brand"):
        committed_receiving_nfb_depth_pair_mm(snap)
    snap = _snapshot()
    snap["nfb_config"]["holes"][0]["source_brand"] = "東元"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    with pytest.raises(ValueError, match="brand"):
        committed_receiving_nfb_depth_pair_mm(snap)


def test_bay_without_unique_provenance_cannot_be_treated_as_selected():
    snap = _snapshot()
    snap.pop("_receiving_runtime_selection")
    snap["receiving_layout"]["sets"][0]["bays"].append(
        {"stable_id": "bayB", "nfb_config_submitted": False}
    )
    with pytest.raises(ValueError, match="ambiguous"):
        committed_receiving_nfb_depth_pair_mm(snap)


def test_existing_gui_base_plate_factory_preserves_source_selected_depths():
    from gui_modules.application.manufacturing_adapter import (
        _base_plate_part_spec_from_values,
    )
    from ae_engine.manufacturing_scene_orchestration import _unfolded_topology_for_spec
    snap = _snapshot(shallow="100_75X130_68.dxf")
    values = {
        **receiving_base_plate_values(snap),
        "model": "受電箱", "w": snap["w"], "t": snap["t"],
    }
    dummy = SimpleNamespace(workspace_controller=SimpleNamespace(
        box_body_structure_state=lambda: {},
        box_body_profile=lambda: (),
    ))
    spec = _base_plate_part_spec_from_values(dummy, values, features=())
    assert spec.receiving_nfb_depth_pair_mm == (107., 68.)
    assert _unfolded_topology_for_spec(spec).width == 780
    # A shared factory must not contaminate a non-Receiving family.
    other = _base_plate_part_spec_from_values(
        dummy, {**values, "model": "金庫型"}, features=()
    )
    assert other.receiving_nfb_depth_pair_mm is None


def test_fold_designer_real_workspace_snapshot_one_set_one_bay_reads_saved_nfb():
    # The GUI snapshot keeps the committed config under receiving_layout, not
    # always as a projected top-level alias.
    snap = _snapshot(shallow="100_75X130_68.dxf")
    snap.pop("nfb_config_submitted")
    snap.pop("nfb_config")
    snap.pop("_receiving_runtime_selection")
    assert committed_receiving_nfb_depth_pair_mm(snap) == (107., 68.)
    assert receiving_base_plate_values(snap)["receiving_nfb_depth_pair_mm"] == (107., 68.)
    assert receiving_base_plate_blank_dimensions(snap) == (780., 240.)


def test_multiple_bays_without_selection_never_leak_another_bay_model():
    snap = _snapshot()
    snap.pop("nfb_config_submitted")
    snap.pop("nfb_config")
    snap.pop("_receiving_runtime_selection")
    snap["receiving_layout"]["sets"][0]["bays"].append({
        "stable_id": "bayB", "nfb_config_submitted": False,
    })
    assert committed_receiving_nfb_depth_pair_mm(snap) is None
    assert receiving_base_plate_values(snap)["receiving_nfb_depth_pair_mm"] is None
    assert receiving_base_plate_blank_dimensions(snap) == (772., 240.)


def test_multiple_bays_selected_runtime_exact_owner_can_use_its_own_saved_models():
    snap = _snapshot(shallow="100_75X130_68.dxf")
    snap.pop("nfb_config_submitted")
    snap.pop("nfb_config")
    snap["receiving_layout"]["sets"][0]["bays"].append({
        "stable_id": "bayB", "nfb_config_submitted": False,
    })
    assert committed_receiving_nfb_depth_pair_mm(snap) == (107., 68.)
    snap["_receiving_runtime_selection"]["bay_id"] = "bayB"
    # A stale mismatched active Bay selection does not produce a false source.
    assert committed_receiving_nfb_depth_pair_mm(snap) is None
