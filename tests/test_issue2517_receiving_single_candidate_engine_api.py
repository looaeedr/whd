# -*- coding: utf-8 -*-
"""Issue #2517 headless single inner-door candidate source Apply."""
from copy import deepcopy
from dataclasses import replace

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import resize_receiving_bays
from ae_engine.receiving_shared_settings import setting_value
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from tests.test_issue1500_receiving_candidate_main_save import _source_with_saved_version


def real_case():
    source, config, _, version = _source_with_saved_version()
    layout = resize_receiving_bays(source["receiving_layout"], set_index=0, bay_count=3)
    return layout, config, version


def test_headless_real_csv_multi_bay_ids_and_source_immutable():
    layout, config, version = real_case()
    old = deepcopy((layout, config))
    new, selected, ids = manufacturing_api.apply_receiving_inner_door_candidate_to_bays(
        layout, config, 0, (2, 1, 2), version_id=version,
    )
    assert selected == (1, 2)
    assert ids == tuple(new["sets"][0]["bays"][i]["stable_id"] for i in selected)
    assert (layout, config) == old
    assert new["sets"][0]["bays"][0] == layout["sets"][0]["bays"][0]
    all_ids = []
    for i in selected:
        row, bay = new["sets"][0], new["sets"][0]["bays"][i]
        assert setting_value(row, i, "inner_door_version_id") == version
        assert setting_value(row, i, "inner_door_models") == config["models"]
        assert bay["nfb_config_submitted"] is True
        for hole in bay["nfb_config"]["holes"]:
            assert hole["manual_x_state"] == "UNVERIFIED_BASIS"
            assert hole["physical_hole_id"].startswith(bay["stable_id"] + ":")
            all_ids.append(hole["physical_hole_id"])
    assert len(all_ids) == len(set(all_ids)) == 4


@pytest.mark.parametrize("bad_set,bad_bays", [
    (True, (1,)), (42, (1,)), (0, ()), (0, (True,)),
    (0, (3,)), (0, ([-1],)), (0, None),
])
def test_invalid_operator_selection_does_not_change_layout(bad_set, bad_bays):
    layout, config, version = real_case()
    old = deepcopy((layout, config))
    with pytest.raises(ValueError):
        manufacturing_api.apply_receiving_inner_door_candidate_to_bays(
            layout, config, bad_set, bad_bays, version_id=version,
        )
    assert (layout, config) == old


def test_invalid_version_fails_closed():
    layout, config, _ = real_case()
    old = deepcopy(layout)
    with pytest.raises(ValueError, match="版本"):
        manufacturing_api.apply_receiving_inner_door_candidate_to_bays(
            layout, config, 0, (1, 2), version_id="head-v1",
        )
    assert layout == old


def test_untrusted_candidate_cannot_replace_submitted_nfb():
    layout, config, version = real_case()
    untrusted = deepcopy(config)
    key = next(iter(untrusted["features"]))
    untrusted["features"][key] = [
        replace(feature, source_type="MANUAL")
        for feature in untrusted["features"][key]
    ]
    old = deepcopy(layout)
    with pytest.raises(ValueError, match="非 CSV 候選"):
        manufacturing_api.apply_receiving_inner_door_candidate_to_bays(
            layout, untrusted, 0, (0, 1), version_id=version,
        )
    assert layout == old


def test_gui_delegates_only_once_to_public_engine(monkeypatch):
    layout, config, version = real_case()
    adapter = ReceivingSetBayAdapter(layout)
    old = deepcopy(adapter.layout)
    real = manufacturing_api.apply_receiving_inner_door_candidate_to_bays
    calls = []
    def record(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)
    monkeypatch.setattr(
        manufacturing_api, "apply_receiving_inner_door_candidate_to_bays", record,
    )
    assert adapter.apply_inner_door_candidate_to_bays(
        config, 0, (2, 1), version_id=version,
    ) == (1, 2)
    assert calls == [1]
    assert adapter.layout["sets"][0]["bays"][0] == old["sets"][0]["bays"][0]
