# -*- coding: utf-8 -*-
"""#2517 RAW manufacturing request physical-source identity is Engine-only."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine import manufacturing_request_parts as source


def test_legacy_vault_and_derived_part_inputs_stay_identical():
    keys = ("box_body", "box_body:left_side", "head", "base_plate:nfb_layer:0", "nfb_pad:1", "door")
    result = manufacturing_api.canonical_manufacturing_request_part_keys(
        {"model": "金庫型"}, keys,
    )
    assert result == ("box_body", "head", "door")
    assert keys == ("box_body", "box_body:left_side", "head", "base_plate:nfb_layer:0", "nfb_pad:1", "door")


def test_actual_committed_receiving_without_manual_workspace_base_adds_source_proven_root():
    from tests.test_receiving_base_physical_3d_z_assembly import _assembled
    snapshot = _assembled()
    before = deepcopy(snapshot)
    keys = manufacturing_api.canonical_manufacturing_request_part_keys(
        snapshot, ("box_body", "head"),
    )
    assert keys == ("box_body", "head", "base_plate")
    assert snapshot == before
    snapshot["nfb_config_submitted"] = False
    assert manufacturing_api.canonical_manufacturing_request_part_keys(
        snapshot, ("box_body", "head"),
    ) == ("box_body", "head")


def test_two_tier_source_replaces_only_legacy_ear_ids_and_keeps_physical_owners(monkeypatch):
    parts = tuple(SimpleNamespace(part_id=f"base_plate:fixing_plate:nfb_layer:{i}:{side}")
                  for i in (0, 1) for side in ("left", "right"))
    calls = []
    def verified(snapshot, *, available_parts):
        calls.append((snapshot, available_parts))
        return parts
    monkeypatch.setattr(source, "receiving_base_fixing_plate_previews", verified)
    snapshot = {"model": "受電箱", "nfb_config_submitted": True,
                "nfb_config": {"layer_count": 2}}
    result = manufacturing_api.canonical_manufacturing_request_part_keys(
        snapshot, ("box_body", "base_plate",
                   "base_plate:fixing_plate:left", "head",
                   "base_plate:nfb_layer:0", "nfb_pad:one"),
    )
    assert result == ("box_body", "base_plate", "head") + tuple(p.part_id for p in parts)
    assert calls == [(snapshot, ("base_plate",))]


def test_unverified_or_stale_two_tier_ear_never_fabricates_parts(monkeypatch):
    def stale(*_args, **_kwargs):
        raise ValueError("EAR_Z_NFB_SOURCE_IDENTITY_DRIFT")
    monkeypatch.setattr(source, "receiving_base_fixing_plate_previews", stale)
    snapshot = {"model": "RECEIVING", "nfb_config_submitted": True,
                "nfb_config": {"layer_count": 2}}
    assert manufacturing_api.canonical_manufacturing_request_part_keys(
        snapshot, ("head", "base_plate:fixing_plate:left"),
    ) == ("head", "base_plate:fixing_plate:left")
    def invalid(*_args, **_kwargs):
        raise ValueError("EAR_PHYSICAL_SOURCE_INVALID")
    monkeypatch.setattr(source, "receiving_base_fixing_plate_previews", invalid)
    with pytest.raises(ValueError, match="EAR_PHYSICAL_SOURCE_INVALID"):
        manufacturing_api.canonical_manufacturing_request_part_keys(snapshot, ("head",))


def test_gui_only_delegates_snapshot_and_workspace_ids(monkeypatch):
    from phase6_manufacturing_adapter import _canonical_part_keys
    seen = []
    def api(snapshot, available_parts):
        seen.append((snapshot, available_parts))
        return ("box_body", "head")
    monkeypatch.setattr(manufacturing_api, "canonical_manufacturing_request_part_keys", api)
    snapshot = {"model": "受電箱"}
    app = SimpleNamespace(_phase6_input_snapshot=snapshot,
                          designer_workspace=SimpleNamespace(available_parts=["box_body", "head"]))
    assert _canonical_part_keys(app) == ("box_body", "head")
    assert seen == [(snapshot, ("box_body", "head"))]
