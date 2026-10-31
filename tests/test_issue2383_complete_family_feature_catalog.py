# -*- coding: utf-8 -*-
"""#2383: every Vault/Receiving function must be visible in installed API.

A catalog entry is never manufacturing proof. Native installed capabilities
may only mark an independently W-03/04/06-certified feature READY.
"""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from integration_cli import cadsplit_worker as worker
from integration_cli.worker_feature_catalog import (
    FAMILIES, _COMMON_OWNERS, _RECEIVING_OWNERS,
    installed_family_feature_catalog,
)

COMMIT = "a" * 40
ENGINE = "b" * 64


def _installed_v11(monkeypatch):
    from integration_cli import private_worker_installation as installation
    source = worker._capabilities(COMMIT, "test-build-only", ENGINE)
    monkeypatch.setattr(worker.sys, "frozen", True, raising=False)
    monkeypatch.setattr(worker.sys, "platform", "win32")
    monkeypatch.setattr(worker, "_capabilities", lambda *args: dict(source))
    monkeypatch.setattr(
        installation, "load_private_execution",
        lambda *args, **kwargs: object(),
    )
    return worker._installed_capabilities(COMMIT, "test-build-only", ENGINE, "signed-01")


def test_full_vault_receiving_feature_catalog_is_schema_valid_and_grounded(monkeypatch):
    advertised = _installed_v11(monkeypatch)
    schema = json.loads((
        Path(__file__).resolve().parents[1] / "integration_cli" / "schemas" /
        "capabilities_v1_1.schema.json"
    ).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(advertised)

    entries = advertised["feature_catalog"]
    expected = {
        f"{family}/{role}"
        for family in FAMILIES
        for role in (_COMMON_OWNERS.keys() | (
            _RECEIVING_OWNERS.keys() if family == "受電箱" else set()
        ))
    }
    indexed = {entry["capability_id"]: entry for entry in entries}
    assert len(indexed) == len(entries) == len(expected)
    assert set(indexed) == expected
    root = Path(__file__).resolve().parents[1]
    assert all((root / row["implementation_owner"]).is_file() for row in entries)
    assert all(
        row["capability_id"] == f'{row["cabinet_family"]}/{row["feature_id"]}'
        for row in entries
    )

    actually_available = {
        (fam, cap["part_kind"])
        for cap in advertised["capabilities"]
        if cap["worker_supported"] and cap["geometry_acceptance_passed"]
        for fam in cap["cabinet_families"]
    }
    assert {(row["cabinet_family"], row["feature_id"])
            for row in entries if row["manufacturing_supported"]} == actually_available
    assert len(actually_available) == 10  # Vault 6 + Receiving 4; standalone custom Fold both families.
    for item in entries:
        assert item["geometry_acceptance_passed"] is item["manufacturing_supported"]
        if item["manufacturing_supported"]:
            assert item["public_operations"] == ["capabilities", "prepare", "export"]
            assert item["blocked_code"] is None
        else:
            assert item["public_operations"] == ["capabilities"]
            assert item["blocked_code"].startswith("WHD_")
    for unsafe in (
        "受電箱/end_cap_head", "受電箱/end_cap_tail",
        "受電箱/box_body", "受電箱/inner_door", "受電箱/divider",
        "受電箱/fixing_plate", "受電箱/multi_bay_batch",
        "金庫型/box_body", "金庫型/base_plate",
    ):
        assert indexed[unsafe]["manufacturing_supported"] is False
        assert indexed[unsafe]["blocked_code"]

    # A listed feature cannot be mistaken for permitted manufacturing.
    assert set(advertised["supported_part_kinds"]) == {
        "door", "indicator_small_door", "indicator_box",
        "end_cap_head", "end_cap_tail", "custom_fold",
    }
    assert not advertised["capability_flags"]["per_part_transactions"]
    assert not advertised["capability_flags"]["crash_recovery"]


def test_capabilities_catalog_fails_closed_when_installed_kind_is_removed(monkeypatch):
    advertised = _installed_v11(monkeypatch)
    caps = dict(advertised)
    caps["capabilities"] = [
        row for row in advertised["capabilities"] if row["part_kind"] != "door"
    ]
    entries = installed_family_feature_catalog(caps)
    assert [x for x in entries if x["feature_id"] == "door"] == [
        {
            "capability_id": f"{family}/door",
            "cabinet_family": family,
            "feature_id": "door",
            "implementation_owner": "ae_engine/manufacturing_api.py",
            "public_operations": ["capabilities"],
            "manufacturing_supported": False,
            "geometry_acceptance_passed": False,
            "production_scope": "part_only",
            "blocked_code": "WHD_CAPABILITY_UNSUPPORTED",
        } for family in FAMILIES
    ]


def test_source_only_api_does_not_claim_installed_feature_catalog():
    response = worker._capabilities(COMMIT, "test-build-only", ENGINE)
    assert response["protocol_version"] == "1.0.0"
    assert response["capabilities"] == []
    assert response["supported_part_kinds"] == []
    assert "feature_catalog" not in response


def test_catalog_schema_refuses_fake_supported_feature_row(monkeypatch):
    from copy import deepcopy
    from jsonschema import ValidationError
    cap = _installed_v11(monkeypatch)
    schema = json.loads((
        Path(__file__).resolve().parents[1] / "integration_cli" / "schemas" /
        "capabilities_v1_1.schema.json"
    ).read_text(encoding="utf-8"))
    corrupt = deepcopy(cap)
    corrupt["feature_catalog"][0]["public_operations"] = ["manufacture_without_signed_job"]
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(corrupt)
