"""#2517: committed Head/Tail CUT replay cannot launder raw physical source."""
from copy import deepcopy
import json

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import operator_relief_replay as replay
from ae_engine.assembly_relief_state import build_current_source_signature


def _values():
    return {"w": 800.0, "h": 1600.0, "d": 350.0,
            "t": 2.0, "fw": 29.0,
            "zl1": 15.0, "zr1": 15.0,
            "yl1": 16.0, "yr1": 16.0,
            "ytop1": 15.0, "ybottom1": 25.0}


def _kwargs(state=None):
    return {
        "relief_state": state if state is not None else {"enabled": True},
        "joint_state": {"assembly_joints": []},
        "structure_state": {"active_type": "integral"},
        "cabinet_family": "金庫型",
        "box_body_profile": [
            {"phase6_key": "fw_left", "len": 25.0, "angle": -90},
            {"phase6_key": "box_w", "len": 350.0, "core": "W"},
            {"phase6_key": "fw_right", "len": 25.0},
        ],
        "part_profiles": {"X": [{"phase6_key": "w", "len": 800.0}]},
    }


@pytest.mark.parametrize("name", ("head", "tail"))
@pytest.mark.parametrize("field,bad", (
    ("w", True), ("w", 0), ("w", float("nan")),
    ("h", False), ("h", "inf"),
    ("d", True), ("d", None),
    ("t", True), ("t", float("nan")),
    ("fw", False), ("fw", "-1"),
    ("zl1", True), ("zr1", "nan"),
    ("yl1", False), ("yr1", "inf"),
    ("ytop1", True), ("ybottom1", float("-inf")),
))
def test_active_replay_rejects_untrusted_original_values_before_fold_or_joint(
    monkeypatch, name, field, bad,
):
    calls = []
    monkeypatch.setattr(
        replay, "formed_box_body_fw_widths",
        lambda *args: calls.append("formed") or (25.0, 25.0),
    )
    monkeypatch.setattr(
        replay, "resolved_joint_graph_fingerprint",
        lambda *args: calls.append("joint") or "joint",
    )
    values = _values()
    values[field] = bad
    before = deepcopy(values)
    kwargs = _kwargs()
    with pytest.raises(ValueError):
        api.resolve_operator_committed_relief_cuts(name, values, **kwargs)
    assert calls == []
    assert values == before


@pytest.mark.parametrize("field", ("w", "h", "d", "t", "fw"))
def test_active_replay_never_replaces_missing_physical_mm_with_zero(field, monkeypatch):
    monkeypatch.setattr(replay, "formed_box_body_fw_widths",
                        lambda *_: pytest.fail("missing source reached Fold owner"))
    values = _values()
    del values[field]
    with pytest.raises(ValueError):
        api.resolve_operator_committed_relief_cuts("head", values, **_kwargs())


def test_active_replay_rejects_non_mapping_before_physical_fold(monkeypatch):
    monkeypatch.setattr(replay, "formed_box_body_fw_widths",
                        lambda *_: pytest.fail("not a mapping"))
    with pytest.raises(ValueError, match="RELIEF_SCALAR_SOURCE_MAPPING_REQUIRED"):
        api.resolve_operator_committed_relief_cuts("head", ["invalid"], **_kwargs())


@pytest.mark.parametrize("disabled", (False, "false", "0", "off"))
def test_disabled_saved_relief_preserves_legacy_uninitialized_short_circuit(
    monkeypatch, disabled,
):
    monkeypatch.setattr(replay, "formed_box_body_fw_widths",
                        lambda *_: pytest.fail("disabled replay reached Fold owner"))
    assert api.resolve_operator_committed_relief_cuts(
        "head", None, relief_state={"enabled": disabled},
    ) == ()


def test_valid_numeric_strings_match_original_saved_replay_and_json_roundtrip(
    monkeypatch,
):
    signatures = []
    original_builder = replay.build_current_source_signature
    def capture(**kw):
        value = original_builder(**kw)
        signatures.append(deepcopy(value))
        return value
    monkeypatch.setattr(replay, "build_current_source_signature", capture)
    values = _values()
    inputs = _kwargs()
    assert api.resolve_operator_committed_relief_cuts(
        "head", values, **inputs,
    ) == ()
    assert signatures
    state = {
        "enabled": True,
        "source": json.loads(json.dumps(signatures[-1])),
        "parts": {"head": {
            "verified": True, "trust_level": "PROVISIONAL_3D",
            "cuts": [[[0, 0], [2, 0], [1, 1]]],
        }},
    }
    positive = dict(inputs, relief_state=state)
    before = deepcopy((values, positive))
    assert api.resolve_operator_committed_relief_cuts(
        "head", values, **positive,
    ) == (((0.0, 0.0), (2.0, 0.0), (1.0, 1.0)),)
    strings = {key: str(value) for key, value in values.items()}
    assert api.resolve_operator_committed_relief_cuts(
        "head", strings, **positive,
    ) == (((0.0, 0.0), (2.0, 0.0), (1.0, 1.0)),)
    assert values == before[0] and positive == before[1]


def test_active_replay_preserves_legacy_optional_fold_defaults(monkeypatch):
    captured = []
    monkeypatch.setattr(replay, "formed_box_body_fw_widths", lambda *args: (None, None))
    monkeypatch.setattr(replay, "resolved_joint_graph_fingerprint",
                        lambda *args: "fingerprint")
    monkeypatch.setattr(replay, "build_current_source_signature",
                        lambda **kwargs: captured.append(kwargs) or kwargs)
    monkeypatch.setattr(replay, "committed_relief_cuts", lambda state, key, source: ())
    values = {key: _values()[key] for key in ("w", "h", "d", "t", "fw")}
    api.resolve_operator_committed_relief_cuts("head", values, **_kwargs())
    assert len(captured) == 1
    assert all(key in captured[0]["scalar_source"] for key in (
        "zl1", "zr1", "yl1", "yr1", "ytop1", "ybottom1",
    ))
