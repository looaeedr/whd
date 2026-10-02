# -*- coding: utf-8 -*-

import pytest


def _snapshot():
    return {"model": "受電箱", "t": 2.0}


def test_receiving_bottom_wrap_defaults_are_linked_for_head_and_tail():
    from phase6_endcap_semantics import normalize_endcap_bottom_wrap_state, resolve_endcap_bottom_wrap

    state = normalize_endcap_bottom_wrap_state(_snapshot())
    assert state["mode"] == "LINKED"
    # Fresh Receiving now defaults to WRAP_OVERLAY, whose BOTTOM edge is fixed WRAP.
    assert resolve_endcap_bottom_wrap(_snapshot(), "head", state=state) == {
        "enabled": True, "reserve_u": 2.0, "reserve_v": 1.0,
    }
    assert resolve_endcap_bottom_wrap(_snapshot(), "tail", state=state) == {
        "enabled": True, "reserve_u": 2.0, "reserve_v": 1.0,
    }


def test_editing_one_endcap_wrap_setting_updates_pair_until_opposite_is_edited():
    from phase6_endcap_semantics import (
        commit_endcap_bottom_wrap,
        normalize_endcap_bottom_wrap_state,
        resolve_endcap_bottom_wrap,
    )

    snap = _snapshot()
    state = normalize_endcap_bottom_wrap_state(snap)
    commit_endcap_bottom_wrap(state, "head", reserve_u=3.5)
    assert state["mode"] == "FOLLOW_HEAD"
    assert resolve_endcap_bottom_wrap(snap, "head", state=state)["reserve_u"] == pytest.approx(3.5)
    assert resolve_endcap_bottom_wrap(snap, "tail", state=state)["reserve_u"] == pytest.approx(3.5)

    commit_endcap_bottom_wrap(state, "head", reserve_v=2.25)
    assert resolve_endcap_bottom_wrap(snap, "tail", state=state) == {
        "enabled": True, "reserve_u": 3.5, "reserve_v": 2.25,
    }

    commit_endcap_bottom_wrap(state, "tail", reserve_u=4.0)
    assert state["mode"] == "INDEPENDENT"
    assert resolve_endcap_bottom_wrap(snap, "head", state=state)["reserve_u"] == pytest.approx(3.5)
    assert resolve_endcap_bottom_wrap(snap, "tail", state=state)["reserve_u"] == pytest.approx(4.0)


def test_non_receiving_default_does_not_enable_receiving_lower_wrap():
    from phase6_endcap_semantics import normalize_endcap_bottom_wrap_state, resolve_endcap_bottom_wrap

    snap = {"model": "金庫型"}
    state = normalize_endcap_bottom_wrap_state(snap)
    assert resolve_endcap_bottom_wrap(snap, "head", state=state)["enabled"] is False
