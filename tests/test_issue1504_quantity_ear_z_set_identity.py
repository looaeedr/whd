# -*- coding: utf-8 -*-
"""#1504 actual quantity Set/Bay identity cannot inherit a stale GUI pointer."""
from copy import deepcopy

import pytest

from ae_engine.receiving_layout import (
    RECEIVING_RUNTIME_SELECTION_KEY,
    new_receiving_layout, project_receiving_bay_legacy_aliases,
)
from ae_engine.receiving_quantity_box import project_common_box
from ae_engine.receiving_tier_ear_z_targets import _current_brand_config
from phase6_quantity_model import QuantityModel
from tests.test_issue1503_nfb_v5_p6fold_roundtrip import _config


def _submitted_quantity_with_old_bay_selection():
    versions=QuantityModel()
    versions.set_version_nfb_config(
        versions.selected_version_id, submitted=True,
        config=_config(two_tiers=True),
    )
    return {
        "model":"受電箱", "active_mode":"quantity", "t":2.,
        "w":800., "h":1600., "d":350.,
        "receiving_quantity_box":{"w":800., "h":1600., "d":350.},
        "quantity":versions.snapshot(),
        "receiving_layout":new_receiving_layout(
            width=800.,height=1600.,depth=350.,
        ),
        RECEIVING_RUNTIME_SELECTION_KEY:{
            "set_index":0, "bay_index":0,
            "set_id":"retired:set:old", "bay_id":"retired:bay:old",
        },
    }


def test_quantity_projection_retains_submitted_v5_but_drops_retired_bay_identity():
    previous=_submitted_quantity_with_old_bay_selection()
    frozen=deepcopy(previous)
    projected=project_common_box(previous)
    assert previous==frozen
    assert RECEIVING_RUNTIME_SELECTION_KEY not in projected
    set_row=projected["receiving_layout"]["sets"][0]
    bay=set_row["bays"][0]
    assert bay["nfb_config_submitted"] is True
    assert projected["nfb_config_submitted"] is True
    assert projected["nfb_config"]==bay["nfb_config"]
    assert len(projected["nfb_config"]["holes"])==2
    # Set/Bay identity may only come from this current projected authority.
    legacy_brand, config=_current_brand_config(projected)
    assert config==projected["nfb_config"]
    assert legacy_brand==set_row["switch_brand"]
    selected=project_receiving_bay_legacy_aliases(projected)
    assert selected[RECEIVING_RUNTIME_SELECTION_KEY]["set_id"]==set_row["stable_id"]
    assert selected[RECEIVING_RUNTIME_SELECTION_KEY]["bay_id"]==bay["stable_id"]
    assert _current_brand_config(selected)[1]==config


def test_ear_z_manufacturing_rejects_explicit_stale_bay_pointer():
    projected=project_common_box(_submitted_quantity_with_old_bay_selection())
    forged={**projected, RECEIVING_RUNTIME_SELECTION_KEY:{
        "set_index":0, "bay_index":0,
        "set_id":"retired:set:old", "bay_id":"retired:bay:old",
    }}
    with pytest.raises(ValueError,match="EAR_Z_SET_IDENTITY_DRIFT"):
        _current_brand_config(forged)
    assert RECEIVING_RUNTIME_SELECTION_KEY not in projected
