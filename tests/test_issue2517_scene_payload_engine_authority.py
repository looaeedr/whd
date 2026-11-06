# -*- coding: utf-8 -*-
"""#2517 manufacturing scene Bay/Joint/Family inputs are owned by Engine."""
from copy import deepcopy

from ae_engine import manufacturing_api as api
from ae_engine import manufacturing_scene_payload as scene
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from ae_engine.receiving_layout import RECEIVING_DOOR_STATE_KEYS


def test_receiving_active_bay_never_allows_stale_global_door_or_nfb():
    source = {
        "model": "受電箱",
        "_receiving_runtime_selection": {"set_id": "s", "bay_id": "b"},
        "nfb_config": {"Bay": "actual"},
        "nfb_config_submitted": True,
    }
    globals_ = {
        "w": 700, "t": 2, "nfb_config": {"Bay": "stale"},
        "nfb_config_submitted": False,
        "receiving_layout": {"sets": ["stale"]},
        "_receiving_runtime_selection": {"bay_id": "stale"},
        **{key: "stale" for key in RECEIVING_DOOR_STATE_KEYS},
    }
    original = deepcopy((source, globals_))
    safe = api.project_manufacturing_scene_settings_overlay(source, globals_)
    assert safe == {"w": 700, "t": 2}
    assert (source, globals_) == original
    merged = {**source, **safe}
    assert merged["nfb_config"] == {"Bay": "actual"}
    assert merged["nfb_config_submitted"] is True


def test_vault_and_unselected_receiving_retain_legacy_global_overlay():
    globals_ = {"w": 600, "nfb_config": {"saved": True}, "door_features": [1]}
    for source in (
        {"model": "金庫型"},
        {"model": "受電箱"},
        {"model": "受電箱", "_receiving_runtime_selection": None},
    ):
        projected = api.project_manufacturing_scene_settings_overlay(source, globals_)
        assert projected == globals_
        assert projected is not globals_


def test_joint_projector_matches_real_legacy_migration_and_is_detached():
    source = {
        "model": "金庫型", "w": 600, "h": 800, "d": 300, "t": 2,
        "existing_parts": ["box_body", "head", "tail"],
        "assembly_type": "INSERT",
    }
    original = deepcopy(source)
    legacy = migrate_legacy_snapshot_joints(source)
    projected = api.project_manufacturing_scene_joint_source(source)
    assert projected == {
        "assembly_joint_schema_version": legacy.get("assembly_joint_schema_version"),
        "assembly_joints": legacy.get("assembly_joints", ()),
    }
    assert source == original
    projected["assembly_joints"].clear()
    assert api.project_manufacturing_scene_joint_source(source)["assembly_joints"] == legacy["assembly_joints"]


def test_bottom_wrap_policy_and_fallback_are_engine_only(monkeypatch):
    called = []
    monkeypatch.setattr(scene.cabinet_family_policy, "supports_bottom_wrap_controls", lambda snap: snap.get("model") == "受電箱")
    monkeypatch.setattr(scene, "resolve_endcap_bottom_wrap", lambda snap, key, *, state: {"reserve_u": 3.0, "reserve_v": 7.0})
    def set_reserves(snap, structure, *, reserve_u, reserve_v):
        called.append((snap, structure, reserve_u, reserve_v))
        return {**structure, "bottom_reserve_u": reserve_u, "bottom_reserve_v": reserve_v}
    monkeypatch.setattr(scene.cabinet_family_policy, "set_bottom_relief_reserves", set_reserves)
    snapshot = {"model": "受電箱"}
    source = {"type": "THREE_PIECE"}
    result = api.project_manufacturing_bottom_relief_structure(
        snapshot, "head", source, bottom_wrap_state={"enabled": True},
    )
    assert result["bottom_reserve_u"] == 3.0 and result["bottom_reserve_v"] == 7.0
    assert source == {"type": "THREE_PIECE"}
    assert called == [(snapshot, source, 3.0, 7.0)]
    assert api.project_manufacturing_bottom_relief_structure(snapshot, "door", source) is source
    assert api.project_manufacturing_bottom_relief_structure({"model": "金庫型"}, "tail", source) is source
    def missing(*_args, **_kwargs):
        raise ValueError("TRANSIENT_BOTTOM_WRAP")
    monkeypatch.setattr(scene, "resolve_endcap_bottom_wrap", missing)
    assert api.project_manufacturing_bottom_relief_structure(snapshot, "head", source) is source


def test_gui_payload_has_only_public_engine_authority_calls():
    from pathlib import Path
    src = Path("phase6_manufacturing_adapter.py").read_text(encoding="utf-8")
    for token in (
        "from ae_engine.assembly_joint import migrate_legacy_snapshot_joints",
        "from ae_engine.cabinet_types import policy as cabinet_family_policy",
        "from ae_engine.receiving_layout import",
    ):
        assert token not in src
    for name in (
        "project_manufacturing_scene_settings_overlay",
        "project_manufacturing_scene_joint_source",
        "project_manufacturing_bottom_relief_structure",
    ):
        assert hasattr(api, name)
        assert "manufacturing_api." + name in src
