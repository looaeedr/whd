"""#2517 Phase6 operator snapshot CornerPolicy is a headless Engine port."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api, resolve_operator_snapshot_corner_policy
from ae_engine.cabinet_types import policy as family_policy
from phase6_manufacturing_adapter import (
    _corner_policy_for_app, operator_finished_dimensions_for_app,
)


def _corners():
    return {key: {"type_id": "CROSS"} for key in (
        "bottom_left", "bottom_right", "top_left", "top_right",
    )}


def test_public_engine_snapshot_policy_keeps_vault_endcap_four_state_and_original_inputs():
    state = {"head": _corners()}
    snapshot = {"model": "金庫型", "fw": 25, "t": 2}
    saved_fw = {
        "mode": "INDEPENDENT",
        "head": {"follow_box": False, "value": 32},
        "tail": {"follow_box": False, "value": 30},
    }
    actual = resolve_operator_snapshot_corner_policy(
        "head", corner_state=state, input_snapshot=snapshot,
        endcap_fw_state=saved_fw,
    )
    assert manufacturing_api.resolve_operator_snapshot_corner_policy is resolve_operator_snapshot_corner_policy
    assert actual.fw == pytest.approx(32.0)
    assert actual.bottom_fw is None
    assert state == {"head": _corners()}
    assert snapshot == {"model": "金庫型", "fw": 25, "t": 2}


def test_receiving_bottom_fw_is_engine_family_policy_only(monkeypatch):
    seen = []
    monkeypatch.setattr(
        family_policy, "supports_bottom_wrap_controls",
        lambda source: source.get("model") == "受電箱",
    )

    def physical_bottom(source, structure, *, thickness, default_fw):
        seen.append((source["model"], structure, thickness, default_fw))
        return 31.0

    monkeypatch.setattr(family_policy, "effective_endcap_bottom_fw", physical_bottom)
    snapshot = {"model": "受電箱", "fw": 25, "t": 2,
                "box_body_structure": {"active_type": "three_piece"}}
    corner_state = {"head": _corners(), "tail": _corners()}
    actual = resolve_operator_snapshot_corner_policy(
        "head", corner_state=corner_state, input_snapshot=snapshot,
    )
    assert actual.fw == pytest.approx(25.0)
    assert actual.bottom_fw == pytest.approx(31.0)
    assert seen == [("受電箱", snapshot["box_body_structure"], 2.0, 25.0)]
    assert resolve_operator_snapshot_corner_policy(
        "head", corner_state=corner_state, input_snapshot={"model": "金庫型", "fw": 25},
    ).bottom_fw is None


def test_missing_or_incomplete_saved_corners_never_invent_policy():
    for corner_state in ({}, {"head": {}}, {"head": {"top_left": {"type_id": "CROSS"}}}):
        assert resolve_operator_snapshot_corner_policy(
            "head", corner_state=corner_state, input_snapshot={"model": "金庫型"},
        ) is None


def test_phase6_adapter_only_passes_operator_inputs(monkeypatch):
    sentinel = object()
    calls = []
    def engine(part_key, **kwargs):
        calls.append((part_key, kwargs))
        return sentinel

    monkeypatch.setattr(manufacturing_api, "resolve_operator_snapshot_corner_policy", engine)
    host = SimpleNamespace(
        _phase6_corner_state={"head": _corners()},
        _phase6_input_snapshot={"model": "受電箱", "fw": 25},
        _settings_values={"t": 2},
        _phase6_endcap_fw_state={"mode": "FOLLOW_BODY"},
    )
    assert _corner_policy_for_app(host, "head") is sentinel
    assert calls == [("head", {
        "corner_state": host._phase6_corner_state,
        "input_snapshot": host._phase6_input_snapshot,
        "settings_values": host._settings_values,
        "endcap_fw_state": host._phase6_endcap_fw_state,
    })]
    source = inspect.getsource(_corner_policy_for_app)
    assert "manufacturing_api.resolve_operator_snapshot_corner_policy(" in source
    for forbidden in ("FourCornerTypePolicy", "policy_from_corner_state",
                      "effective_endcap_bottom_fw", "supports_bottom_wrap_controls"):
        assert forbidden not in source
    engine_source = inspect.getsource(resolve_operator_snapshot_corner_policy)
    assert "phase6_" not in engine_source
    assert "tkinter" not in engine_source


def test_box_body_live_dimensions_pass_both_engine_policies(monkeypatch):
    calls = []
    head = object()
    tail = object()
    monkeypatch.setattr(
        manufacturing_api, "resolve_operator_snapshot_corner_policy",
        lambda part_key, **kwargs: calls.append(part_key) or
        (head if part_key == "head" else tail),
    )
    def dims(part_key, **kwargs):
        assert part_key == "box_body"
        assert kwargs["head_corner_policy"] is head
        assert kwargs["tail_corner_policy"] is tail
        return (400.0, 600.0, 250.0)
    monkeypatch.setattr(manufacturing_api, "resolve_live_operator_finished_dimensions", dims)
    host = SimpleNamespace(
        active_part_key="box_body",
        _phase6_corner_state={},
        _phase6_input_snapshot={"model": "金庫型"},
        _settings_values={},
        _phase6_box_whd={},
    )
    assert operator_finished_dimensions_for_app(host) == (400.0, 600.0, 250.0)
    assert calls == ["head", "tail"]
