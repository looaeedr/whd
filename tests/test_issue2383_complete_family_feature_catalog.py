# -*- coding: utf-8 -*-
"""#2383 feature catalog remains internal metadata after installed Worker retirement."""
from integration_cli import cadsplit_worker as worker
from integration_cli.worker_feature_catalog import (
    FAMILIES, _COMMON_OWNERS, _RECEIVING_OWNERS,
    installed_family_feature_catalog,
)

COMMIT = "a" * 40
ENGINE = "b" * 64


def test_source_only_api_does_not_claim_feature_catalog():
    response = worker._capabilities(COMMIT, "test-build-only", ENGINE)
    assert response["protocol_version"] == "1.0.0"
    assert response["capabilities"] == []
    assert response["supported_part_kinds"] == []
    assert "feature_catalog" not in response


def test_internal_feature_catalog_without_enabled_caps_is_all_blocked():
    source = worker._capabilities(COMMIT, "test-build-only", ENGINE)
    entries = installed_family_feature_catalog(source)
    expected = {
        f"{family}/{role}"
        for family in FAMILIES
        for role in (_COMMON_OWNERS.keys() | (
            _RECEIVING_OWNERS.keys() if family == "受電箱" else set()
        ))
    }
    indexed = {entry["capability_id"]: entry for entry in entries}
    assert set(indexed) == expected
    assert all(row["manufacturing_supported"] is False for row in entries)
    assert all(row["geometry_acceptance_passed"] is False for row in entries)
    assert all(row["public_operations"] == ["capabilities"] for row in entries)
    assert all(row["blocked_code"] for row in entries)
