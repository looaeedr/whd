"""#2517: serialized Fold mirror flags must not change physical removal truth."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import operator_fold_editor as owner


MIRROR_ROWS = (
    {"len": 12, "phase6_key": "fw_left"},
    {"len": 100, "phase6_key": "w"},
    {"len": 12, "phase6_key": "fw_right"},
)
REMOVE_ROWS = (
    {"len": 12, "angle": 90},
    {"len": 100, "core": "W", "angle": 90},
    {"len": 12},
)


@pytest.mark.parametrize("raw,normalized", [
    (False, False), (True, True),
    ("false", False), ("FALSE", False), ("off", False), ("0", False),
    ("true", True), ("ON", True), ("1", True), ("yes", True),
    (0, False), (1, True),
])
def test_public_fold_mirror_policy_matches_native_bool_for_serialized_sources(
    raw, normalized,
):
    original = deepcopy(MIRROR_ROWS)
    for legacy in (False, True):
        actual = api.plan_operator_fold_mirror_target(
            MIRROR_ROWS, 0, "len",
            is_box_body=raw, resolve_legacy_position=legacy,
        )
        expected = api.plan_operator_fold_mirror_target(
            MIRROR_ROWS, 0, "len",
            is_box_body=normalized, resolve_legacy_position=legacy,
        )
        assert actual == expected
    assert MIRROR_ROWS == original


@pytest.mark.parametrize("raw,normalized", [
    (False, False), (True, True),
    ("false", False), ("OFF", False), ("true", True), ("on", True),
    (0, False), (1, True),
])
def test_public_fold_legacy_fallback_matches_canonical_serialized_flag(raw, normalized):
    actual = api.plan_operator_fold_mirror_target(
        MIRROR_ROWS, 0, "len",
        is_box_body=False, resolve_legacy_position=raw,
    )
    expected = api.plan_operator_fold_mirror_target(
        MIRROR_ROWS, 0, "len",
        is_box_body=False, resolve_legacy_position=normalized,
    )
    assert actual == expected
    assert (actual.target_index is None) is (not normalized)


@pytest.mark.parametrize("raw,enabled", [
    (False, False), (True, True), ("false", False),
    ("OFF", False), ("true", True), ("ON", True), (0, False), (1, True),
])
def test_symmetric_removal_same_physical_parts_as_native_bool(raw, enabled):
    original = deepcopy(REMOVE_ROWS)
    actual = api.operator_fold_editor_remove_segment(
        REMOVE_ROWS, 0, 2.0, symmetric_box_body=raw,
    )
    expected = api.operator_fold_editor_remove_segment(
        REMOVE_ROWS, 0, 2.0, symmetric_box_body=enabled,
    )
    assert actual == expected
    assert len(actual) == (1 if enabled else 2)
    assert REMOVE_ROWS == original
    assert json.loads(json.dumps(actual)) == actual


@pytest.mark.parametrize("bad", [
    "2", "not-a-bool", None, 2, -1, 1.5,
    "NaN", float("nan"), float("inf"), [], {},
])
@pytest.mark.parametrize("port", [
    "is_box_body", "resolve_legacy_position", "symmetric_box_body",
])
def test_bad_raw_fold_mirror_flag_rejects_before_any_material_result(bad, port):
    source = deepcopy(REMOVE_ROWS)
    before = deepcopy(source)
    with pytest.raises(ValueError, match="布林值"):
        if port == "symmetric_box_body":
            api.operator_fold_editor_remove_segment(
                source, 0, 2.0, symmetric_box_body=bad,
            )
        else:
            kwargs = {"is_box_body": False, "resolve_legacy_position": False}
            kwargs[port] = bad
            api.plan_operator_fold_mirror_target(
                source, 0, "len", **kwargs,
            )
    assert source == before


def test_public_engine_semantics_are_same_canonical_boolean_owner():
    assert api.plan_operator_fold_mirror_target is owner.plan_operator_fold_mirror_target
    assert api.operator_fold_editor_remove_segment is owner.operator_fold_editor_remove_segment
    plan = inspect.getsource(owner.plan_operator_fold_mirror_target)
    remove = inspect.getsource(owner.operator_fold_editor_remove_segment)
    assert "normalize_operator_settings_boolean(is_box_body)" in plan
    assert "normalize_operator_settings_boolean(" in plan
    assert "normalize_operator_settings_boolean(symmetric_box_body)" in remove
    assert "from phase6_" not in inspect.getsource(owner)
