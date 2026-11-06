"""#2517 navigation must not save hidden Receiving projections over live Bay."""
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.fold_designer_part_session import Phase6PartSessionOwner


SOURCE = {"model": "受電箱", "active_mode": "set_bay"}
STORED = {"X": [{"phase6_key": "yl1", "len": 15.0}],
          "Y": [{"phase6_key": "fw", "len": 25.0}]}
LIVE = {"w": "820", "h": "1600", "d": "360"}
COMMITTED = {"w": 820, "h": 1600, "d": 360}


def decide(snapshot=None, **overrides):
    params = dict(previous_active="head", save_outgoing=True,
                  was_non_single=False, stored_profiles=deepcopy(STORED),
                  live_profiles=deepcopy(STORED),
                  live_dimensions=dict(LIVE),
                  committed_dimensions=dict(COMMITTED))
    params.update(overrides)
    return api.can_skip_operator_receiving_part_save(
        dict(SOURCE) if snapshot is None else snapshot, **params,
    )


@pytest.mark.parametrize("family", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_unchanged_head_tail_and_hidden_assembly_are_display_only(family):
    snap = {"model": family, "active_mode": "set_bay"}
    for part in ("head", "tail"):
        assert decide(snap, previous_active=part) is True
    assert decide(snap, previous_active="box_body", was_non_single=True,
                  live_profiles=None, live_dimensions=None) is True
    assert decide(snap, previous_active="box_body", was_non_single=False) is False
    assert decide(snap, previous_active="base_plate") is False


@pytest.mark.parametrize("source", [
    {"model": "金庫型", "active_mode": "set_bay"},
    {"model": "受電箱", "active_mode": "quantity"},
    {"model": "受電箱", "active_mode": ""},
    {"model": "UNSUPPORTED", "active_mode": "set_bay"},
    {},
])
def test_only_receiving_set_bay_may_skip(source):
    assert decide(source) is False
    assert decide(source, previous_active="box_body",
                  was_non_single=True) is False


def test_actual_edit_and_missing_source_never_skipped():
    edited = deepcopy(STORED)
    edited["X"][0]["len"] += 0.1
    assert decide(live_profiles=edited) is False
    assert decide(live_dimensions={**LIVE, "w": "821"}) is False
    assert decide(live_dimensions={**LIVE, "w": "not-a-number"}) is False
    assert decide(live_dimensions={**LIVE, "w": "nan"}) is False
    assert decide(live_dimensions=None) is False
    assert decide(live_profiles=None) is False
    assert decide(committed_dimensions={"w": 820}) is False
    assert decide(save_outgoing=False) is False
    assert decide(previous_active="tail", live_dimensions={**LIVE, "w": "820.0000000001"}) is True


def test_inputs_are_read_only_and_gui_delegates_entire_save_decision():
    source = deepcopy(SOURCE)
    stored = deepcopy(STORED)
    assert decide(source, stored_profiles=stored) is True
    assert source == SOURCE and stored == STORED
    activation = inspect.getsource(Phase6PartSessionOwner.activate_part)
    assert "manufacturing_api.can_skip_operator_receiving_part_save(" in activation
    assert "skip_hidden_receiving_assembly_save" not in activation
    assert "skip_unchanged_receiving_endcap_save" not in activation
    assert "unchanged_fold" not in activation
    assert "unchanged_whd" not in activation
    from ae_engine import operator_part_session_profiles as owner
    assert "from gui_modules" not in inspect.getsource(owner)
