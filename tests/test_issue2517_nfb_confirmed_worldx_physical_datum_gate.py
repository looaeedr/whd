# -*- coding: utf-8 -*-
"""#2517: a stale CONFIRMED CSV NFB world-X must not reach canonical CUTTING.

This is the existing public Engine source path used by GUI and headless
manufacturing.  The selected Bay and root config may be exactly equal while
a prior width/model/rotation datum has become invalid.
"""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine import receiving_nfb_committed_final_scene as engine
from ae_engine.cabinet_types import policy
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_nfb_model_identity import numeric_model_ref


def _selected_snapshot(*, bay_width=800, datum=None):
    model = numeric_model_ref("士林", "2P400")
    row = {
        "physical_hole_id": "nfb:v5:one",
        "source_brand": "士林",
        "model_filename": model,
        "layer_index": 0,
        "slot_index": 0,
        "layer_count": 1,
        "manual_x_state": "CONFIRMED",
        "manual_x_mm": 0.0,
        "datum_revision": "CURRENT-PHYSICAL-BAY-PROOF",
        "datum_snapshot": datum if datum is not None else {
            "width": 800, "model_filename": model, "rotation_deg": 0,
        },
        "rotation_deg": 0,
    }
    config = {"layer_count": 1, "holes": [row]}
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout = deepcopy(layout)
    selected = layout["sets"][0]["bays"][0]
    selected["width"] = bay_width
    selected["nfb_config_submitted"] = True
    selected["nfb_config"] = deepcopy(config)
    return {
        "model": "受電箱",
        "nfb_config_submitted": True,
        "nfb_config": deepcopy(config),
        "receiving_layout": layout,
        "_receiving_runtime_selection": {
            "set_index": 0, "bay_index": 0,
            "set_id": layout["sets"][0]["stable_id"],
            "bay_id": selected["stable_id"],
        },
    }


@pytest.mark.parametrize("bay_width,datum", (
    (750, None),
    (800, {"width": 800, "model_filename": "nfbv5:士林:invalid", "rotation_deg": 0}),
    (800, {"width": 800, "rotation_deg": 90}),
    (800, {"model_filename": numeric_model_ref("士林", "2P400")}),
))
def test_stale_confirmed_world_x_fails_before_finalscene_source(
    monkeypatch, bay_width, datum,
):
    snapshot = _selected_snapshot(bay_width=bay_width, datum=datum)
    before = deepcopy(snapshot)

    def must_not_build_panel(_snapshot):
        pytest.fail("stale world X reached physical panel CUTTING")

    monkeypatch.setattr(policy, "derive_inner_door_panels", must_not_build_panel)
    with pytest.raises(
        ValueError, match="NFB_COMMITTED_CSV_CONFIRMED_DATUM_STALE",
    ):
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
            snapshot,
        )
    assert snapshot == before


def test_current_confirmed_world_x_remains_eligible_for_physical_panel_resolution(
    monkeypatch,
):
    snapshot = _selected_snapshot()
    before = deepcopy(snapshot)

    def current_panel_would_build(_snapshot):
        raise RuntimeError("REACHED_CANONICAL_PHYSICAL_PANEL")

    monkeypatch.setattr(
        policy, "derive_inner_door_panels", current_panel_would_build,
    )
    with pytest.raises(RuntimeError, match="REACHED_CANONICAL_PHYSICAL_PANEL"):
        engine._submitted_csv_holes(snapshot)
    assert snapshot == before
