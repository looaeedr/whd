"""#2517: all manufacturing cache-key semantic decisions belong to headless Engine."""
from __future__ import annotations

from copy import deepcopy
from enum import Enum
import inspect
import re

import pytest

from ae_engine import manufacturing_api
from phase6_manufacturing_adapter import build_manufacturing_cache_key
from phase6_manufacturing_geometry import (
    _phase6_manufacturing_state_signature,
    _phase6_signature_canonical_value,
)
from phase6_sync_envelope import stable_fingerprint
from tests.test_issue359_manufacturing_cache_service import _app


def _fingerprint(app):
    return build_manufacturing_cache_key(app).fingerprint


def test_public_owner_and_phase6_is_only_state_extraction():
    assert callable(manufacturing_api.manufacturing_state_fingerprint)
    assert callable(manufacturing_api.canonical_manufacturing_signature_value)
    assert "manufacturing_api.manufacturing_state_fingerprint(" in inspect.getsource(
        _phase6_manufacturing_state_signature
    )
    assert "manufacturing_api.canonical_manufacturing_signature_value(value)" in inspect.getsource(
        _phase6_signature_canonical_value
    )
    body = inspect.getsource(_phase6_manufacturing_state_signature)
    for legacy_rule in ("ui_text_size", "mirror_keys", "RECEIVING", "受電箱",
                        "stable_fingerprint(", "settings.update("):
        assert legacy_rule not in body
    import ae_engine.manufacturing_cache_signature as engine
    assert "phase6_" not in inspect.getsource(engine)
    assert "tkinter" not in inspect.getsource(engine)


def test_existing_real_adapter_cache_key_preserves_previous_exact_digest():
    app = _app()
    # This tuple is the pre-migration canonical state for the unchanged
    # issue359 live adapter fixture; it is not a new manufacturing formula.
    old_state = (
        {"model": "金庫型", "w": 800.0, "h": 1800.0, "d": 400.0},
        {"t": 2.0},
        {"w": 800.0, "h": 1800.0, "d": 400.0},
        {}, {}, {},
        ("box_body",),
        {"box_body": {}},
        "INSERT_OVERLAY", False, 0.0,
    )
    assert _fingerprint(app) == stable_fingerprint(old_state)


def test_ui_typography_and_persisted_mirrors_do_not_invalidate_geometry():
    app = _app()
    baseline = _fingerprint(app)
    app._settings_values["ui_text_size"] = "extra large"
    for key, val in (
        ("part_dimensions", {"door": {"width": 400}}),
        ("active_part", "tail"),
        ("settings", {"t": 2}),
        ("corner_state", {"head": "mirror"}),
        ("endcap_fw", {"head": 20}),
        ("endcap_bottom_wrap", {"head": 30}),
    ):
        app._phase6_input_snapshot[key] = val
    assert _fingerprint(app) == baseline
    app._phase6_corner_state["head"] = {"corner": "CROSS"}
    assert _fingerprint(app) != baseline


def test_receiving_working_box_dimensions_override_seed_settings_only():
    a = _app()
    a._phase6_input_snapshot["model"] = "受電箱"
    a._settings_values.update({"w": 700, "h": 1500, "d": 300})
    b = deepcopy(a)
    b._settings_values.update({"w": 1, "h": 2, "d": 3})
    assert _fingerprint(a) == _fingerprint(b)
    b._phase6_box_whd["w"] = 900
    assert _fingerprint(a) != _fingerprint(b)
    a._phase6_input_snapshot["model"] = "金庫型"
    b = deepcopy(a)
    b._settings_values["w"] = 999
    assert _fingerprint(a) != _fingerprint(b)


def test_fold_and_assembly_intent_invalidate_key_independent_of_presentation():
    app = _app()
    baseline = _fingerprint(app)
    app.designer_workspace = type("Workspace", (), {
        "available_parts": ("box_body",),
        "profiles_for": lambda self, part, default: {
            "X": [{"len": 22.0, "angle": -90, "tag": {"operator": ["x"]}}]
        },
    })()
    folded = _fingerprint(app)
    assert folded != baseline
    app.designer_workspace.profiles_for = lambda key, default: {"X": [
        {"len": 22.0, "angle": -90, "tag": {"operator": ["x"]}}
    ]}
    assert _fingerprint(app) == folded
    app._phase6_assembly_type.value = "OVERLAY"
    assert _fingerprint(app) != folded


class _Side(Enum):
    LEFT = "left"


def test_canonicalizer_stable_numeric_and_unordered_equality():
    value = {"x": (1, 2.00000000000004), "tags": {"b", "a"},
             "orientation": _Side.LEFT, "bool": True}
    expected = {"x": (1.0, 2.0), "tags": ("a", "b"),
                "orientation": "left", "bool": True}
    assert manufacturing_api.canonical_manufacturing_signature_value(value) == expected
    assert _phase6_signature_canonical_value(value) == expected


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), 10 ** 1000])
def test_invalid_material_state_does_not_share_cache_key_with_literal_marker(bad):
    app = _app()
    app._settings_values["fw"] = bad
    with pytest.raises(ValueError, match="nonfinite manufacturing signature value"):
        _fingerprint(app)
    app._settings_values["fw"] = "__NaN__"
    assert re.fullmatch(r"[0-9a-f]{64}", _fingerprint(app))


def test_engine_request_works_without_tk_and_does_not_mutate_inputs():
    snapshot = {"model": "RECEIVING", "w": 300, "part_dimensions": {"door": 4}}
    settings = {"w": 400, "ui_text_size": "tiny"}
    box = {"w": 800}
    profiles = {"head": {"X": [{"len": 20, "meta": {"token": ["x"]}}]}}
    originals = deepcopy((snapshot, settings, box, profiles))
    kwargs = dict(input_snapshot=snapshot, settings_values=settings,
                  working_box=box, corner_state={}, endcap_fw_state={},
                  endcap_bottom_wrap_state={}, available_parts=("head",),
                  part_profiles=profiles, assembly_intent="INSERT",
                  ignore_fixed_corner=False, relief_clearance=0.0)
    digest = manufacturing_api.manufacturing_state_fingerprint(**kwargs)
    assert re.fullmatch("[0-9a-f]{64}", digest)
    assert (snapshot, settings, box, profiles) == originals
    kwargs["part_profiles"] = {"head": {"X": [{"len": 21}]}}
    assert manufacturing_api.manufacturing_state_fingerprint(**kwargs) != digest
