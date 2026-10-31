# -*- coding: utf-8 -*-
"""#2517: Receiving NFB candidate source and Bay physical IDs are Engine-owned."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from tests.test_issue1500_receiving_candidate_main_save import _source_with_saved_version


def _case():
    source, config, part_id, version = _source_with_saved_version()
    return source, config, part_id, version


def test_real_csv_candidate_uses_engine_source_and_retains_unverified_x():
    _, config, part_id, _ = _case()
    frozen = deepcopy(config)
    result = manufacturing_api.candidate_committed_csv_nfb_config(config)
    assert result["layer_count"] == config["layers"]
    assert len(result["holes"]) == 2
    assert all(h["manual_x_state"] == "UNVERIFIED_BASIS" for h in result["holes"])
    assert all(h["manual_x_mm"] is None for h in result["holes"])
    assert all(h["physical_hole_id"].startswith(part_id + ":nfb:")
               for h in result["holes"])
    assert config == frozen


def test_mixed_cutting_and_two_sources_fail_closed():
    _, config, part_id, _ = _case()
    mixed = deepcopy(config)
    mixed["features"]["manual"] = [SimpleNamespace(
        layer="CUTTING", source_type="USER",
    )]
    with pytest.raises(ValueError, match="雙重開孔"):
        manufacturing_api.candidate_committed_csv_nfb_config(mixed)
    duplicate = deepcopy(config)
    duplicate["features"]["inner_door:other:panel"] = deepcopy(
        duplicate["features"][part_id],
    )
    with pytest.raises(ValueError, match="唯一實體"):
        manufacturing_api.candidate_committed_csv_nfb_config(duplicate)
    assert manufacturing_api.candidate_committed_csv_nfb_config(
        {"features": {}},
    ) is None


def test_engine_scopes_real_bay_ids_without_mutating_saved_candidate():
    source, config, _, _ = _case()
    adapter = ReceivingSetBayAdapter(source["receiving_layout"])
    adapter.set_bay_count(2)
    layout = adapter.layout
    frozen = deepcopy(layout)
    csv = manufacturing_api.candidate_committed_csv_nfb_config(config)
    updated = manufacturing_api.replace_candidate_bay_nfb(layout, 0, 1, csv)
    assert layout == frozen and updated is not layout
    bays = updated["sets"][0]["bays"]
    assert bays[0] == frozen["sets"][0]["bays"][0]
    assert bays[1]["nfb_config_submitted"] is True
    assert all(h["physical_hole_id"].startswith(bays[1]["stable_id"] + ":")
               and h["manual_x_state"] != "CONFIRMED"
               for h in bays[1]["nfb_config"]["holes"])
    assert not any(h["physical_hole_id"].startswith(bays[1]["stable_id"] + ":")
                   for h in csv["holes"])


def test_engine_rejects_non_csv_replacement_of_submitted_bay():
    source, _, _, _ = _case()
    layout = source["receiving_layout"]
    candidate = {"features": {"inner_door": [SimpleNamespace(layer="CUTTING")]}}
    with pytest.raises(ValueError, match="雙重 CUTTING"):
        manufacturing_api.validate_candidate_nfb_replacement(
            layout, ((0, 0),), candidate, None,
        )
    manufacturing_api.validate_candidate_nfb_replacement(
        layout, ((0, 0),), {"features": {}}, None,
    )


def test_real_gui_candidate_apply_uses_only_engine_ports(monkeypatch):
    source, config, _, version = _case()
    adapter = ReceivingSetBayAdapter(source["receiving_layout"])
    adapter.set_bay_count(2)
    original = deepcopy(adapter.layout)
    calls = []
    for name in (
        "candidate_committed_csv_nfb_config",
        "validate_candidate_nfb_replacement",
        "replace_candidate_bay_nfb",
    ):
        fn = getattr(manufacturing_api, name)
        def record(*args, _name=name, _fn=fn, **kwargs):
            calls.append(_name)
            return _fn(*args, **kwargs)
        monkeypatch.setattr(manufacturing_api, name, record)
    assert adapter.apply_inner_door_candidate_to_bays(
        config, 0, (1,), version_id=version,
    ) == (1,)
    assert calls == [
        "candidate_committed_csv_nfb_config",
        "validate_candidate_nfb_replacement",
        "replace_candidate_bay_nfb",
    ]
    assert adapter.layout["sets"][0]["bays"][0] == original["sets"][0]["bays"][0]
    assert adapter.layout["sets"][0]["bays"][1]["nfb_config_submitted"] is True
