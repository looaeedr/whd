"""#2517 raw manufacturing inventory must use the registered physical Family.

An alias cannot omit a current submitted NFB BasePlate or four physical fixing
ears from the same Engine request. This is RAW source identity, not DXF release.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_base_fixing_plate import receiving_base_fixing_plate_previews
from phase6_manufacturing_adapter import (
    _canonical_part_keys, build_manufacturing_request,
)
from tests.test_issue1502_source_derived_center_base import _source_snapshot
from tests.test_receiving_two_tier_physical_base_parts import _two_tier
from tests.test_issue356_manufacturing_adapter import _fake_app


RAW = ("box_body", "head", "tail")
ALIASES = ("受電箱", "RECEIVING", "receiving", " ReCeIvInG ")


@pytest.mark.parametrize("family", ALIASES)
def test_single_tier_committed_real_nfb_base_has_same_raw_engine_part_inventory(family):
    canonical = _source_snapshot(shallow="2P400")
    expected = api.canonical_manufacturing_request_part_keys(canonical, RAW)
    assert "base_plate" in expected
    aliased = deepcopy(canonical)
    aliased["model"] = family
    old = deepcopy(aliased)
    result = api.canonical_manufacturing_request_part_keys(aliased, RAW)
    assert result == expected
    assert result.count("base_plate") == 1
    assert aliased == old


@pytest.mark.parametrize("family", ALIASES)
def test_two_real_nfb_tiers_retain_one_base_and_exact_engine_ear_owners(family):
    canonical = _two_tier()
    expected = api.canonical_manufacturing_request_part_keys(canonical, RAW)
    expected_ears = tuple(
        piece.part_id for piece in receiving_base_fixing_plate_previews(
            canonical, available_parts=("base_plate",),
        )
    )
    assert len(expected_ears) == 4 and len(set(expected_ears)) == 4
    assert "base_plate" in expected
    assert tuple(key for key in expected if key.startswith("base_plate:fixing_plate:")) == expected_ears
    snapshot = deepcopy(canonical)
    snapshot["model"] = family
    before = deepcopy(snapshot)
    selected = api.canonical_manufacturing_request_part_keys(snapshot, RAW)
    assert selected == expected
    assert snapshot == before


def test_gui_immutable_request_for_real_submitted_nfb_alias_includes_same_base():
    base = _source_snapshot(shallow="2P400")
    for family in ALIASES:
        app = _fake_app()
        app._phase6_input_snapshot = {**deepcopy(base), "model": family}
        app.baseline_model_var.value = family
        raw = _canonical_part_keys(app)
        assert raw == api.canonical_manufacturing_request_part_keys(
            app._phase6_input_snapshot,
            tuple(app.designer_workspace.available_parts),
        )
        request = build_manufacturing_request(app)
        assert tuple(request.canonical_part_keys) == raw
        assert "base_plate" in request.canonical_part_keys
        assert "base_plate" in {part.part_key for part in request.parts}
        assert request.cabinet_model == family.strip()


@pytest.mark.parametrize("family", ("金庫型", "VAULT", "RO", "UNKNOWN"))
def test_other_families_never_gain_receiving_physical_parts_from_stale_nfb(family):
    source = _two_tier()
    source["model"] = family
    assert api.canonical_manufacturing_request_part_keys(source, RAW) == RAW


def test_unsubmitted_receiving_does_not_create_physical_base_or_ear():
    source = _two_tier()
    source["model"] = "receiving"
    source["nfb_config_submitted"] = False
    assert api.canonical_manufacturing_request_part_keys(source, RAW) == RAW


def test_saved_cabinet_type_alias_uses_registered_family_for_real_single_base():
    source = _source_snapshot(shallow="2P400")
    source.pop("model")
    source["cabinet_type"] = "receiving"
    assert "base_plate" in api.canonical_manufacturing_request_part_keys(source, RAW)


def test_public_engine_owns_model_identity_not_gui_string_comparisons():
    import inspect

    body = inspect.getsource(api.canonical_manufacturing_request_part_keys)
    assert "canonical_family_name(snapshot)" in body
    assert 'snapshot.get("model") in (' not in body
    gui = inspect.getsource(_canonical_part_keys)
    assert "manufacturing_api.canonical_manufacturing_request_part_keys(" in gui
