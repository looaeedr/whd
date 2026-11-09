# -*- coding: utf-8 -*-
"""#2517 Divider Family fold chain/indices remain Engine-qualified sources."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine.cabinet_types import policy, receiving
from ae_engine.door_dividers import derive_box_body_dividers


def valid_contract():
    return {
        "material_lengths": (16., 25., 102., 15.),
        "signed_fold_chain": (18., 29., 106., 17.),
        "formed_core_depth": 106.,
        "core_segment_index": 2,
        "frame_width_segment_index": 1,
    }


def real_divider(**kwargs):
    return derive_box_body_dividers(
        ((800., (1100., 500.)),),
        depth=kwargs.get("depth", 350.),
        thickness=kwargs.get("thickness", 2.),
        frame_width=kwargs.get("frame_width", 29.),
        handle_edges={},
        layout_scope="receiving-main",
        model_name="受電箱",
    )


def test_valid_receiving_family_chain_matches_original_and_real_divider():
    direct = policy.divider_fold_contract(
        "受電箱", depth=350, thickness=2, frame_width=29, handle_side=False,
    )
    original = receiving.divider_fold_contract(
        depth=350, thickness=2, frame_width=29, handle_side=False,
    )
    assert direct == original == valid_contract()
    parts = real_divider()
    assert len(parts) == 1
    actual = parts[0]
    assert actual.material_lengths == direct["material_lengths"]
    assert actual.signed_fold_chain == direct["signed_fold_chain"]
    assert actual.core_segment_index == 2
    assert actual.frame_width_segment_index == 1
    assert actual.blank_width == pytest.approx(sum(valid_contract()["material_lengths"]))
    assert actual.fold_profile and actual.fold_profile[0].length == 16.


@pytest.mark.parametrize("raw,expected", [
    ("29", 29.), ("29.125", 29.125), (29.125, 29.125),
])
def test_original_family_uses_exact_serialized_and_fractional_operator_fw(raw, expected):
    saved = json.loads(json.dumps({"frame_width": raw, "thickness": "2"}))
    before = deepcopy(saved)
    result = policy.divider_fold_contract(
        "受電箱", depth="350", thickness=saved["thickness"],
        frame_width=saved["frame_width"], handle_side="false",
    )
    assert result["signed_fold_chain"][1] == expected
    assert result["material_lengths"][1] == pytest.approx(expected - 4.0)
    assert saved == before


@pytest.mark.parametrize("name", ["depth", "thickness", "frame_width"])
@pytest.mark.parametrize("bad", [
    True, False, 0, -1, "0", "nan", "inf", float("nan"), "bad",
])
def test_invalid_physical_input_stops_before_family_dispatch(monkeypatch, name, bad):
    monkeypatch.setattr(
        policy, "_call",
        lambda *a, **kw: pytest.fail("invalid family input must not reach fold"),
    )
    values = dict(depth=350., thickness=2., frame_width=29., handle_side=False)
    values[name] = bad
    with pytest.raises(ValueError):
        policy.divider_fold_contract("受電箱", **values)


def test_optional_frame_width_none_retains_original_receiving_family_default():
    # Omitted Divider FW is a supported Family default, not a malformed T.
    projected = policy.divider_fold_contract(
        "受電箱", depth=350, thickness=2, frame_width=None,
        handle_side=False,
    )
    expected = receiving.divider_fold_contract(
        depth=350, thickness=2, frame_width=None, handle_side=False,
    )
    assert projected == expected
    assert projected["material_lengths"] == (16., 25., 102., 15.)


@pytest.mark.parametrize("name", ["depth", "thickness"])
def test_missing_required_physical_source_stops_before_dispatch(monkeypatch, name):
    monkeypatch.setattr(
        policy, "_call",
        lambda *a, **kw: pytest.fail("missing required D/T must not dispatch"),
    )
    kwargs = dict(depth=350., thickness=2., handle_side=False, frame_width=29.)
    kwargs[name] = None
    with pytest.raises(ValueError):
        policy.divider_fold_contract("受電箱", **kwargs)


@pytest.mark.parametrize("bad", [None, "bad", "2", 2, float("nan")])
def test_bad_handle_side_stops_before_family_dispatch(monkeypatch, bad):
    monkeypatch.setattr(
        policy, "_call",
        lambda *a, **kw: pytest.fail("invalid handle source must not dispatch"),
    )
    with pytest.raises(ValueError):
        policy.divider_fold_contract(
            "受電箱", depth=350, thickness=2, frame_width=29,
            handle_side=bad,
        )


@pytest.mark.parametrize("field,bad", [
    ("material_lengths", [16., True, 102., 15.]),
    ("material_lengths", [16., float("nan"), 102., 15.]),
    ("material_lengths", [16., float("inf"), 102., 15.]),
    ("signed_fold_chain", [18., False, 106., 17.]),
    ("signed_fold_chain", [18., float("nan"), 106., 17.]),
    ("signed_fold_chain", [18., float("inf"), 106., 17.]),
    ("formed_core_depth", True),
    ("formed_core_depth", 0),
    ("formed_core_depth", -1),
    ("formed_core_depth", float("nan")),
    ("formed_core_depth", float("inf")),
    ("core_segment_index", True),
    ("core_segment_index", 1.5),
    ("core_segment_index", "1.5"),
    ("core_segment_index", float("nan")),
    ("frame_width_segment_index", False),
    ("frame_width_segment_index", 2.5),
    ("frame_width_segment_index", "2.5"),
    ("frame_width_segment_index", float("inf")),
])
def test_malformed_family_output_rejected_before_real_fold_profile(
    monkeypatch, field, bad,
):
    original = valid_contract()
    payload = {**original, field: bad}
    before = repr(payload)
    monkeypatch.setattr(policy, "_call", lambda *a, **kw: payload)
    with pytest.raises(ValueError, match="family Divider"):
        real_divider()
    assert repr(payload) == before


@pytest.mark.parametrize("field,bad", [
    ("material_lengths", [16., True, 102., 15.]),
    ("signed_fold_chain", [18., float("nan"), 106., 17.]),
    ("formed_core_depth", float("nan")),
    ("core_segment_index", 2.5),
    ("frame_width_segment_index", False),
])
def test_headless_family_contract_rejects_same_bad_outputs(monkeypatch, field, bad):
    source = {**valid_contract(), field: bad}
    monkeypatch.setattr(policy, "_call", lambda *a, **kw: source)
    with pytest.raises(ValueError):
        policy.divider_fold_contract(
            "受電箱", depth=350, thickness=2, frame_width=29, handle_side=True,
        )


def test_family_integral_float_and_legacy_string_indices_remain_compatible(monkeypatch):
    saved = {**valid_contract(), "core_segment_index": "2",
             "frame_width_segment_index": 1.0}
    monkeypatch.setattr(policy, "_call", lambda *a, **kw: saved)
    r = policy.divider_fold_contract(
        "受電箱", depth=350, thickness=2, frame_width=29, handle_side=True,
    )
    assert r["core_segment_index"] == 2
    assert r["frame_width_segment_index"] == 1
    assert r["signed_fold_chain"] == tuple(saved["signed_fold_chain"])


def test_family_divider_has_no_lossy_engine_source_coercion():
    src = inspect.getsource(policy.divider_fold_contract)
    assert "normalize_operator_source_dimension(depth, field=\"d\")" in src
    assert "normalize_operator_source_dimension(thickness, field=\"t\")" in src
    assert "normalize_operator_settings_boolean(handle_side)" in src
    assert "_divider_family_segment_index(" in src
    assert "tuple(float(v)" not in src
    assert "int(data.get(" not in src
