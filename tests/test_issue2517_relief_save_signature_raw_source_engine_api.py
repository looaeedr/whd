"""#2517 persisted Assembly Relief signature source validates raw mm before provenance."""
from copy import deepcopy
import json

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import operator_relief_replay as owner


def _sources():
    scalar = {
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0,
        "zl1": 15.0, "zl2": 0.0, "zr1": 15.0, "zr2": 0.0,
        "yl1": 16.0, "yr1": 16.0, "ytop1": 15.0, "ybottom1": 25.0,
    }
    kwargs = dict(
        scalar_source=scalar,
        joint_state={"assembly_joints": []},
        structure_state={"active_type": "integral"},
        box_body_profile=[
            {"phase6_key": "fw_left", "len": 25.0, "angle": -90},
            {"phase6_key": "box_w", "len": 350.0, "core": "W"},
            {"phase6_key": "fw_right", "len": 25.0},
        ],
        part_profiles={"head": {"X": [
            {"phase6_key": "w", "len": 800.0},
        ]}},
    )
    return kwargs


@pytest.mark.parametrize("field,bad", (
    ("w", True), ("w", 0), ("w", "nan"),
    ("h", False), ("h", float("inf")),
    ("d", True), ("d", None),
    ("t", False), ("t", float("nan")),
    ("fw", True), ("fw", "-2"),
    ("zl1", True), ("zl2", "nan"),
    ("zr1", False), ("zr2", float("inf")),
    ("yl1", True), ("yr1", "inf"),
    ("ytop1", False), ("ybottom1", float("-inf")),
))
def test_persisted_signature_rejects_invalid_raw_source_before_physical_owner(
    monkeypatch, field, bad,
):
    monkeypatch.setattr(owner, "formed_box_body_fw_widths",
                        lambda *a: pytest.fail("bad Save source entered Fold owner"))
    monkeypatch.setattr(owner, "resolved_joint_graph_fingerprint",
                        lambda *a: pytest.fail("bad Save source entered Joint owner"))
    kw = _sources()
    kw["scalar_source"][field] = bad
    before = deepcopy(kw)
    with pytest.raises(ValueError):
        api.build_operator_current_relief_source_signature(**kw)
    assert kw == before


@pytest.mark.parametrize("field", ("w", "h", "d", "t", "fw"))
def test_persisted_signature_never_uses_zero_for_absent_physical_field(field):
    kw = _sources()
    del kw["scalar_source"][field]
    with pytest.raises(ValueError):
        api.build_operator_current_relief_source_signature(**kw)


def test_persisted_signature_keeps_raw_valid_fractional_strings_but_uses_exact_t(
    monkeypatch,
):
    kw = _sources()
    kw["scalar_source"]["t"] = "2.125"
    kw["scalar_source"]["fw"] = "29.25"
    kw["scalar_source"]["w"] = "800.125"
    kw["scalar_source"]["yl1"] = "-16.5"
    before = deepcopy(kw)
    calls = []
    original = owner.formed_box_body_fw_widths
    def capture(profile, thickness):
        calls.append(thickness)
        return original(profile, thickness)
    monkeypatch.setattr(owner, "formed_box_body_fw_widths", capture)
    current = api.build_operator_current_relief_source_signature(**kw)
    assert calls == [2.125]
    assert current["w"] == "800.125"
    assert current["t"] == "2.125"
    assert current["fw"] == "29.25"
    assert current["yl1"] == "-16.5"
    assert current["box_body_formed_fw"]["left"] is not None
    assert kw == before
    assert json.loads(json.dumps(current, ensure_ascii=False)) == current


def test_valid_numeric_original_source_uses_same_signed_source_serializer():
    kw = _sources()
    before = deepcopy(kw)
    original = api.build_operator_current_relief_source_signature(**kw)
    assert original["w"] == 800.0
    assert original["t"] == 2.0
    assert original["cabinet_family"] == "受電箱"
    assert "joint_graph_fingerprint" in original
    assert kw == before


def test_invalid_joint_state_still_rejected_before_formed_source(monkeypatch):
    monkeypatch.setattr(owner, "formed_box_body_fw_widths",
                        lambda *a: pytest.fail("invalid joint should not form"))
    kw = _sources()
    kw["joint_state"] = []
    with pytest.raises(ValueError, match="RELIEF_JOINT_SOURCE_MAPPING_REQUIRED"):
        api.build_operator_current_relief_source_signature(**kw)
