# -*- coding: utf-8 -*-
"""#2517 manufacturing input acquisition must not mask invalid physical sources."""
from types import SimpleNamespace

import pytest

import phase6_manufacturing_adapter as adapter


def _failing(*args, **kwargs):
    raise RuntimeError("physical source read failed")


def test_invalid_box_body_profile_readback_does_not_fall_back_to_snapshot(monkeypatch):
    monkeypatch.setattr(adapter, "read_box_body_profile", _failing)
    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "金庫型", "w": 400, "h": 500, "d": 200, "t": 2},
        _settings_values={},
        _phase6_box_whd={},
        state=SimpleNamespace(profiles_vault={"箱身": [{"len": 200}]}),
    )
    payload = adapter.build_scene_payload_for_app(app, "box_body")
    assert payload["_manufacturing_profile_readback_error"] == (
        "MANUFACTURING_SCENE_PROFILE_INVALID:box_body"
    )
    assert payload["w"] == 400  # A draft preview still renders its operator input.
    with pytest.raises(ValueError, match="MANUFACTURING_SCENE_PROFILE_INVALID:box_body"):
        adapter._scene_values_for_part(app, "box_body", builder=lambda _: payload)


def test_invalid_endcap_profile_readback_does_not_fall_back_to_snapshot(monkeypatch):
    monkeypatch.setattr(adapter, "read_endcap_xy_profiles", _failing)
    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "金庫型", "w": 400, "h": 500, "d": 200, "t": 2},
        _settings_values={},
        _phase6_box_whd={},
        designer_workspace=SimpleNamespace(active_part="head"),
        state=SimpleNamespace(profiles={"X": [{"len": 100}], "Y": [{"len": 200}]}),
    )
    payload = adapter.build_scene_payload_for_app(app, "head")
    assert payload["_manufacturing_profile_readback_error"] == (
        "MANUFACTURING_SCENE_PROFILE_INVALID:head"
    )
    with pytest.raises(ValueError, match="MANUFACTURING_SCENE_PROFILE_INVALID:head"):
        adapter._scene_values_for_part(app, "head", builder=lambda _: payload)


@pytest.mark.parametrize("raw", [1, True, "bad", object()])
def test_invalid_operator_mapping_cannot_be_downgraded_to_empty(raw):
    with pytest.raises(ValueError, match="MANUFACTURING_INPUT_MAPPING_INVALID"):
        adapter._mapping(raw)


def test_valid_or_absent_mapping_retains_legacy_compatibility():
    assert adapter._mapping(None) == {}
    assert adapter._mapping({}) == {}
    assert adapter._mapping([("w", 400)]) == {"w": 400}


def test_workspace_provider_failure_does_not_silently_erase_features():
    workspace = SimpleNamespace(features_for=_failing)
    with pytest.raises(ValueError, match="MANUFACTURING_WORKSPACE_INPUT_FAILED:features_for:head") as error:
        adapter._workspace_value(workspace, "features_for", "head", ())
    assert isinstance(error.value.__cause__, RuntimeError)
    assert adapter._workspace_value(workspace, "missing_method", "head", ()) == ()


def test_structure_provider_failure_does_not_silently_erase_physical_parts():
    workspace = SimpleNamespace(box_body_structure_state=_failing)
    with pytest.raises(ValueError, match="MANUFACTURING_BOX_BODY_STRUCTURE_UNAVAILABLE") as error:
        adapter._box_body_structure(workspace)
    assert isinstance(error.value.__cause__, RuntimeError)
    assert adapter._box_body_structure(SimpleNamespace()) == {}


def test_malformed_input_snapshot_aborts_before_manufacturing_request():
    app = SimpleNamespace(_phase6_input_snapshot=42)
    with pytest.raises(ValueError, match="MANUFACTURING_INPUT_MAPPING_INVALID"):
        adapter.build_manufacturing_request(app)


def test_manufacturing_request_aborts_on_unverified_draft_profile(monkeypatch):
    monkeypatch.setattr(adapter, "read_box_body_profile", _failing)
    monkeypatch.setattr(adapter, "_canonical_part_keys", lambda app: ("box_body",))
    app = SimpleNamespace(
        _phase6_input_snapshot={"model": "金庫型", "w": 400, "h": 500, "d": 200, "t": 2},
        _settings_values={"t": 2},
        _phase6_box_whd={"w": 400, "h": 500, "d": 200},
        state=SimpleNamespace(profiles_vault={"箱身": [{"len": 200}]}),
        designer_workspace=SimpleNamespace(available_parts=("box_body",)),
    )
    with pytest.raises(ValueError, match="MANUFACTURING_SCENE_PROFILE_INVALID:box_body"):
        adapter.build_manufacturing_request(
            app,
            scene_payload_builder=lambda key: adapter.build_scene_payload_for_app(app, key),
        )
