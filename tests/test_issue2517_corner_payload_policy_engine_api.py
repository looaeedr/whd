"""#2517: CornerType payload manufacturing policy belongs to public Engine."""
from __future__ import annotations
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import corner_policy_from_payload, manufacturing_api
from ae_engine.corner_type_ui import known_model_corner_state, policy_from_corner_state
from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, CrossCornerMode, CornerDirection,
)
from gui_modules.application import fold_designer_manufacturing_projection as adapter


def _corners(value=None):
    return {"head": {
        corner: ({"type_id": "CROSS"} if value is None else value)
        for corner in ("top_left", "top_right", "bottom_left", "bottom_right")
    }}


def test_public_engine_raw_payload_preserves_operator_corner_types():
    assert corner_policy_from_payload is manufacturing_api.corner_policy_from_payload
    state = _corners()
    state["head"]["top_left"] = {
        "type_id": "CROSS", "cross_mode": "retain",
        "direction": "width", "amount_t": 1.5,
    }
    state["head"]["top_right"] = {"type_id": "OVERLAY"}
    state["head"]["bottom_left"] = {"type_id": "INSERT"}
    state["head"]["bottom_right"] = {"type_id": "INSERT_OVERLAY"}
    policy = corner_policy_from_payload(state, "head", 29)
    assert policy.fw == 29.0
    assert policy.top_left.cross_mode is CrossCornerMode.RETAIN
    assert policy.top_left.direction is CornerDirection.WIDTH
    assert policy.top_left.amount_t == 1.5
    assert policy.top_right.type_id is CornerTypeId.OVERLAY
    assert policy.bottom_left.type_id is CornerTypeId.INSERT
    assert policy.bottom_right.type_id is CornerTypeId.INSERT_OVERLAY


def test_existing_typed_legacy_c02_input_normalizes_inside_engine():
    state = _corners()
    state["head"]["top_left"] = CornerTypeSelection(CornerTypeId.C02, 1)
    result = corner_policy_from_payload(state, "head", 25)
    assert result.top_left.type_id is CornerTypeId.CROSS
    assert result.top_left.cross_mode is CrossCornerMode.RETAIN
    assert result.top_left.direction is CornerDirection.HEIGHT


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_only_explicit_known_family_uses_registry_fallback(family):
    partial = {"head": {"top_left": {"type_id": "CROSS"}}}
    assert corner_policy_from_payload(partial, "head", 25) is None
    result = corner_policy_from_payload(
        partial, "head", 25, known_family=family,
    )
    expected = policy_from_corner_state(
        known_model_corner_state(("head",), cabinet_family=family)["head"], fw=25,
    )
    assert result == expected
    manual = _corners({"type_id": "OVERLAY"})
    result = corner_policy_from_payload(
        manual, "head", 25, known_family=family,
    )
    assert all(getattr(result, corner).type_id is CornerTypeId.OVERLAY
               for corner in ("top_left", "top_right", "bottom_left", "bottom_right"))


def test_missing_and_invalid_corner_payload_fails_closed():
    assert corner_policy_from_payload(None, "tail", 25) is None
    with pytest.raises(ValueError):
        corner_policy_from_payload(_corners({"type_id": "NOT_A_CORNER"}), "head", 25)
    with pytest.raises((ValueError, TypeError)):
        corner_policy_from_payload(_corners({"type_id": "CROSS", "rotation_quadrants": "invalid"}), "head", 25)


def test_gui_only_passes_payload_and_known_family_to_engine(monkeypatch):
    seen = []
    sentinel = object()
    def engine(state, part, fw, *, known_family=None):
        seen.append((state, part, fw, known_family))
        return sentinel
    monkeypatch.setattr(manufacturing_api, "corner_policy_from_payload", engine)
    state = _corners()
    assert adapter._fold_designer_corner_policy_from_payload(state, "head", 29) is sentinel
    host = SimpleNamespace(
        _fold_designer_corner_policy_from_payload=lambda *args: None,
        _current_cabinet_type_name=lambda: "受電箱",
        _apply_cabinet_family_endcap_policy=lambda result, part, **kw: result,
    )
    assert adapter._payload_policy(host, {"box_body_structure": {}}, state, "head", 29, False, 2) is sentinel
    assert seen == [(state, "head", 29, None), (state, "head", 29, "受電箱")]
    source = inspect.getsource(adapter._fold_designer_corner_policy_from_payload)
    fallback = inspect.getsource(adapter._payload_policy)
    assert "manufacturing_api.corner_policy_from_payload(" in source + fallback
    for forbidden in ("CornerTypeSelection(", "policy_from_corner_state(",
                      "known_model_corner_state("):
        assert forbidden not in source + fallback
