"""#2517: full Fold Designer CornerType selection belongs to one public Engine API."""
from copy import deepcopy
from inspect import getsource
from types import SimpleNamespace

import ae_engine
import pytest
from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_manufacturing_projection as gui

_CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")


def _state(kind="CROSS"):
    return {"head": {key: {"type_id": kind} for key in _CORNERS}}


def _original_chain(corners, part, fw, *, family, unknown, source, thickness):
    """Existing Engine primitives: parity oracle, never an alternative GUI owner."""
    raw = api.corner_policy_from_payload(corners, part, fw)
    if raw is None and not unknown:
        raw = api.corner_policy_from_payload(corners, part, fw, known_family=family)
    return api.apply_cabinet_family_endcap_policy(
        raw, part, family_source=source,
        structure_state=source.get("box_body_structure"), thickness=thickness,
    )


def test_same_callable_from_engine_root_and_public_facade():
    assert (ae_engine.resolve_operator_fold_designer_payload_corner_policy
            is api.resolve_operator_fold_designer_payload_corner_policy)
    assert "resolve_operator_fold_designer_payload_corner_policy" in ae_engine.__all__


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("part", ("head", "tail", "door"))
def test_complete_operator_corner_state_precedes_family_registry(family, part):
    corners = {part: _state("OVERLAY")["head"]}
    original = deepcopy(corners)
    source = {"model": family}
    before = deepcopy(source)
    expected = _original_chain(
        corners, part, 25, family=family, unknown=False, source=source,
        thickness=2.0,
    )
    actual = api.resolve_operator_fold_designer_payload_corner_policy(
        corners, part, 25, known_family=family, unknown=False,
        family_source=source, thickness=2.0,
    )
    assert actual == expected
    assert all(getattr(actual, key).type_id.value == "OVERLAY" for key in _CORNERS)
    assert corners == original and source == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_missing_corners_use_same_certified_family_fallback_and_lower_fw(family):
    source = {"model": family}
    corners = {"head": {"top_left": {"type_id": "CROSS"}}}
    before = deepcopy((source, corners))
    expected = _original_chain(
        corners, "head", 25, family=family, unknown=False, source=source,
        thickness=2.0,
    )
    result = api.resolve_operator_fold_designer_payload_corner_policy(
        corners, "head", 25, known_family=family, unknown=False,
        family_source=source, thickness=2.0,
    )
    assert result == expected
    assert result is not None
    assert (source, corners) == before


def test_unknown_model_cannot_borrow_vault_or_receiving_registry():
    source = {"model": "自訂"}
    original = deepcopy(source)
    partial = {"head": {"bottom_left": {"type_id": "INSERT"}}}
    before = deepcopy(partial)
    assert api.resolve_operator_fold_designer_payload_corner_policy(
        partial, "head", 25, known_family="金庫型", unknown=True,
        family_source=source, thickness=2.0,
    ) is None
    assert source == original and partial == before


@pytest.mark.parametrize("value", ("bad", None, 1, 0))
def test_bad_unknown_flag_rejects_without_changes(value):
    state = _state()
    source = {"model": "金庫型"}
    before = deepcopy((state, source))
    with pytest.raises(ValueError, match="boolean"):
        api.resolve_operator_fold_designer_payload_corner_policy(
            state, "head", 25, known_family="金庫型", unknown=value,
            family_source=source, thickness=2.0,
        )
    assert (state, source) == before


def test_invalid_corner_rejects_atomically():
    state = _state("INVALID")
    source = {"model": "金庫型"}
    before = deepcopy((state, source))
    with pytest.raises(ValueError):
        api.resolve_operator_fold_designer_payload_corner_policy(
            state, "head", 25, known_family="金庫型", unknown=False,
            family_source=source, thickness=2.0,
        )
    assert (state, source) == before


def test_fold_designer_real_adapter_is_one_engine_call(monkeypatch):
    calls = []
    sentinel = object()
    def engine(state, part, fw, **options):
        calls.append((state, part, fw, options))
        return sentinel
    monkeypatch.setattr(
        api, "resolve_operator_fold_designer_payload_corner_policy", engine,
    )
    state = _state()
    source = {"model": "受電箱", "box_body_structure": {"source": 42}}
    host = SimpleNamespace()
    assert gui._payload_policy(host, source, state, "head", 25, False, 2) is sentinel
    assert calls == [(state, "head", 25, {
        "unknown": False,
        "family_source": source, "thickness": 2,
        "structure_state": source["box_body_structure"],
    })]
    body = getsource(gui._payload_policy)
    assert "resolve_operator_fold_designer_payload_corner_policy(" in body
    assert "corner_policy_from_payload(" not in body
    assert "apply_cabinet_family_endcap_policy(" not in body
    assert "if resolved is None" not in body

@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_incomplete_policy_infers_certified_family_only_inside_engine(family):
    source = {"model": family}
    partial = {"head": {"top_left": {"type_id": "CROSS"}}}
    original = deepcopy((source, partial))
    expected = _original_chain(
        partial, "head", 25, family=family, unknown=False,
        source=source, thickness=2.0,
    )
    assert api.resolve_operator_fold_designer_payload_corner_policy(
        partial, "head", 25, unknown=False,
        family_source=source, thickness=2.0,
    ) == expected
    assert (source, partial) == original
