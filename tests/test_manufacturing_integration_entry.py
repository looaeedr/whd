"""Headless CADSplit/WHD integration entry contract and fail-closed tests."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ae_engine import (
    ManufacturingIntegrationRequest,
    ManufacturingSourceIdentity,
    dispatch_manufacturing_integration,
)
from ae_engine import manufacturing_api


@pytest.mark.parametrize("family,canonical", [
    ("金庫型", "金庫型"),
    ("VAULT", "金庫型"),
    ("受電箱", "受電箱"),
    ("RECEIVING", "受電箱"),
])
def test_prepare_accepts_source_reference_without_claiming_manufacturing(family, canonical):
    source = ManufacturingSourceIdentity(
        panel_key="panel-a", source_revision="source-dxf-sha",
        set_id="source-set-1", bay_id="source-bay-1",
    )
    result = manufacturing_api.dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("prepare", family=family, source=source)
    )
    assert result.family == canonical
    assert result.source is source
    assert result.status == "SOURCE_ACCEPTED_NOT_MANUFACTURING_READY"
    assert result.python_api_available is True
    assert not result.manufacturing_authorized
    assert not result.dxf_roundtrip_verified
    assert not result.external_export_available
    assert not hasattr(result, "physical_part_id")


def test_capabilities_report_registration_without_manufacturing_authorization():
    result = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("capabilities")
    )
    assert result.status == "SOURCE_API_AVAILABLE"
    assert {"金庫型", "受電箱", "RO"}.issubset(set(result.known_families))
    assert not result.external_export_available
    assert not result.manufacturing_authorized
    ro = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("capabilities", family="落地盤")
    )
    assert ro.family == "RO"
    assert ro.family_implemented is False
    assert not ro.manufacturing_authorized


@pytest.mark.parametrize("source", [
    None,
    object(),
    ManufacturingSourceIdentity("", "source-sha"),
    ManufacturingSourceIdentity("panel", ""),
    ManufacturingSourceIdentity("panel", "sha", set_id="set"),
    ManufacturingSourceIdentity("panel", "sha", bay_id="bay"),
    ManufacturingSourceIdentity("panel", "sha", set_id="  ", bay_id="bay"),
])
def test_missing_or_partial_source_is_blocked(source):
    result = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("prepare", family="受電箱", source=source)
    )
    assert result.status == "SOURCE_REQUIRED"
    assert not result.manufacturing_authorized


def test_ro_unimplemented_and_unknown_family_fail_closed():
    source = ManufacturingSourceIdentity("panel", "sha")
    for family, status in (("RO", "UNSUPPORTED_FAMILY"), ("UNKNOWN", "UNSUPPORTED_FAMILY")):
        result = dispatch_manufacturing_integration(
            ManufacturingIntegrationRequest("prepare", family=family, source=source)
        )
        assert result.status == status
        assert not result.manufacturing_authorized


def test_external_export_never_writes_or_invokes_existing_exporter(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("External source cannot reach manufacturing without certified Engine state")
    monkeypatch.setattr(manufacturing_api, "generate_part", forbidden)
    monkeypatch.setattr(manufacturing_api, "save_resolved_manufacturing_geometry_batch_dxf", forbidden)
    result = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest(
            "export", family="受電箱",
            source=ManufacturingSourceIdentity("panel", "sha", "set", "bay"),
        )
    )
    assert result.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"
    assert not result.manufacturing_authorized
    assert not result.dxf_roundtrip_verified
    assert list(tmp_path.iterdir()) == []


def test_unknown_operation_and_bad_request_are_blocked():
    with pytest.raises(TypeError, match="ManufacturingIntegrationRequest"):
        dispatch_manufacturing_integration(object())
    result = dispatch_manufacturing_integration(
        ManufacturingIntegrationRequest("delete_everything", family="金庫型")
    )
    assert result.status == "UNSUPPORTED_OPERATION"


def test_entry_requests_and_source_are_immutable():
    source = ManufacturingSourceIdentity("panel", "sha")
    request = ManufacturingIntegrationRequest("prepare", family="金庫型", source=source)
    with pytest.raises(FrozenInstanceError):
        source.panel_key = "tampered"
    with pytest.raises(FrozenInstanceError):
        request.family = "受電箱"
