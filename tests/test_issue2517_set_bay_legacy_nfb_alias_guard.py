# -*- coding: utf-8 -*-
"""#2517: a stale legacy root alias must not hide a submitted physical Bay NFB.

The root may be a historical DXF projection, but it cannot replace the
persistent identity of the selected Set/Bay's actual NFBConfig. No geometric
hole position, slot pitch, or export approval is inferred by this test.
"""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_nfb_model_identity import numeric_model_ref


def _legacy_config():
    return {
        "layer_count": 1, "holes": [{
            "physical_hole_id": "nfb:legacy:one",
            "model_filename": "HISTORIC_2P400.dxf",
            "layer_index": 0, "slot_index": 0,
            "manual_x_state": "NONE",
        }],
    }


def _numeric_config():
    return {
        "layer_count": 1, "holes": [{
            "physical_hole_id": "nfb:v5:one",
            "model_filename": numeric_model_ref("士林", "2P400"),
            "source_brand": "士林", "layer_index": 0,
            "slot_index": 0, "layer_count": 1,
            "manual_x_state": "UNVERIFIED_BASIS",
            "rotation_deg": 0,
        }],
    }


def _snapshot(*, submitted=True, saved_config=None, selector=True):
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    bay = layout["sets"][0]["bays"][0]
    if submitted:
        bay["nfb_config_submitted"] = True
        bay["nfb_config"] = deepcopy(
            _numeric_config() if saved_config is None else saved_config
        )
    snapshot = {
        "model": "受電箱",
        "active_mode": "set_bay",
        "receiving_layout": layout,
        "nfb_config_submitted": True,
        "nfb_config": _legacy_config(),
    }
    if selector:
        snapshot["_receiving_runtime_selection"] = {
            "set_index": 0, "bay_index": 0,
            "set_id": layout["sets"][0]["stable_id"],
            "bay_id": bay["stable_id"],
        }
    return snapshot


@pytest.mark.parametrize("selector", (True, False))
def test_submitted_physical_csv_bay_cannot_be_hidden_by_legacy_root(selector):
    snapshot = _snapshot(selector=selector)
    original = deepcopy(snapshot)
    with pytest.raises(ValueError, match="NFB_COMMITTED_CSV_BAY_IDENTITY_DRIFT"):
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
            snapshot,
        )
    assert snapshot == original


def test_genuine_selected_legacy_bay_keeps_pre_v5_route():
    snapshot = _snapshot(saved_config=_legacy_config())
    original = deepcopy(snapshot)
    assert manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
        snapshot,
    ) is None
    assert snapshot == original


def test_unsubmitted_selected_bay_does_not_invent_csv_hole():
    snapshot = _snapshot(submitted=False)
    assert manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
        snapshot,
    ) is None


def test_unresolved_multi_bay_selection_cannot_hide_submitted_nfb():
    snapshot = _snapshot(selector=False)
    other = deepcopy(snapshot["receiving_layout"]["sets"][0]["bays"][0])
    other["stable_id"] = "receiving:set:1:bay:2"
    other["panel_name"] = "P2"
    other.pop("nfb_config_submitted", None)
    other.pop("nfb_config", None)
    snapshot["receiving_layout"]["sets"][0]["bays"].append(other)
    original = deepcopy(snapshot)
    with pytest.raises(
        ValueError, match="NFB_COMMITTED_CSV_ACTIVE_BAY_SELECTION_UNRESOLVED",
    ):
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
            snapshot,
        )
    assert snapshot == original


def test_unsubmitted_selected_bay_is_not_replaced_by_another_bay():
    snapshot = _snapshot(selector=False)
    other = deepcopy(snapshot["receiving_layout"]["sets"][0]["bays"][0])
    other["stable_id"] = "receiving:set:1:bay:2"
    other["panel_name"] = "P2"
    other.pop("nfb_config_submitted", None)
    other.pop("nfb_config", None)
    snapshot["receiving_layout"]["sets"][0]["bays"].append(other)
    snapshot["_receiving_runtime_selection"] = {
        "set_index": 0, "bay_index": 1,
        "set_id": snapshot["receiving_layout"]["sets"][0]["stable_id"],
        "bay_id": other["stable_id"],
    }
    original = deepcopy(snapshot)
    assert manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
        snapshot,
    ) is None
    assert snapshot == original


def test_legacy_root_only_snapshot_remains_compatible():
    snapshot = {"model": "受電箱", "nfb_config_submitted": True,
                "nfb_config": _legacy_config()}
    assert manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
        snapshot,
    ) is None
