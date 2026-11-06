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


def _engine_resolved_door(part_key="door"):
    """Minimal canonical container; writer and independent verifier are test doubles."""
    from types import SimpleNamespace
    from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart

    render = SimpleNamespace(scene=object(), metadata={})
    return ResolvedManufacturingGeometry(
        parts=(ResolvedManufacturingPart(part_key=part_key, render_data=render),),
    )


def _source_bay(set_id="SetA", bay_id="Bay1", *, source_revision="sha-123"):
    from ae_engine import ManufacturingResolvedBayInput
    return ManufacturingResolvedBayInput(
        family="RECEIVING",
        source=ManufacturingSourceIdentity("panel-A", source_revision, set_id, bay_id),
        resolved_geometry=_engine_resolved_door(),
    )


def test_verified_resolved_receiving_bays_stage_all_parts_before_commit(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pathlib import Path
    from ae_engine import export_verified_resolved_integration_bays
    from ae_engine import manufacturing_verification

    events = []
    def writer(render_data, path, *, overwrite):
        assert overwrite is True
        assert ".whd-dxf-stage-" in str(path)
        Path(path).write_text("real writer simulated", encoding="utf-8")
        events.append("stage")

    def verifier(render_data, path, **kwargs):
        assert ".whd-dxf-stage-" in str(path)
        assert Path(path).read_text(encoding="utf-8") == "real writer simulated"
        events.append("reopen")
        return SimpleNamespace(ok=True)

    def guard():
        events.append("guard")

    monkeypatch.setattr(manufacturing_api, "save_part_render_data_dxf", writer)
    monkeypatch.setattr(manufacturing_verification, "verify_saved_part_render_data_dxf", verifier)
    result = export_verified_resolved_integration_bays(
        (_source_bay(), _source_bay("SetA", "Bay2")),
        tmp_path / "out", pre_commit_guard=guard,
    )
    assert events == ["guard", "stage", "reopen", "stage", "reopen", "guard"]
    assert len(result.output_files) == 2
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert not result.external_cli_enabled
    assert set(Path(p).name for p in result.output_files.values()) == {
        "SetA__Bay1__door.dxf", "SetA__Bay2__door.dxf",
    }
    for value in result.output_files.values():
        assert Path(value).is_file()
    with pytest.raises(TypeError):
        result.output_files["injected"] = "x"


@pytest.mark.parametrize("invalid", [
    (),
    (_source_bay("S", "B"), _source_bay("S", "B")),
    (_source_bay("S", "B"), _source_bay("s", "b")),
    (_source_bay("a/b", "c"), _source_bay("a_b", "c")),
])
def test_verified_bay_export_rejects_empty_or_colliding_source(tmp_path, invalid):
    from ae_engine import export_verified_resolved_integration_bays
    with pytest.raises(ValueError):
        export_verified_resolved_integration_bays(
            invalid, tmp_path / "out", pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "out").exists()


def test_verified_bay_requires_engine_resolved_geometry_not_raw_source(tmp_path):
    from dataclasses import replace
    from ae_engine import export_verified_resolved_integration_bays
    bad = replace(_source_bay(), resolved_geometry={"raw_dxf": "not an Engine result"})
    with pytest.raises(ValueError, match="RECEIVING_ENGINE_RESOLVED_GEOMETRY_REQUIRED"):
        export_verified_resolved_integration_bays(
            (bad,), tmp_path / "out", pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "out").exists()


def test_verified_bay_guard_and_family_fail_closed(tmp_path):
    from dataclasses import replace
    from ae_engine import export_verified_resolved_integration_bays
    candidate = _source_bay()
    with pytest.raises(ValueError, match="WHD_PRECOMMIT_GUARD_REQUIRED"):
        export_verified_resolved_integration_bays(
            (candidate,), tmp_path / "out", pre_commit_guard=None,
        )
    with pytest.raises(ValueError, match="WHD_VERIFIED_BAY_RECEIVING_ONLY"):
        export_verified_resolved_integration_bays(
            (replace(candidate, family="VAULT"),), tmp_path / "out",
            pre_commit_guard=lambda: None,
        )
    with pytest.raises(ValueError, match="RECEIVING_STABLE_SOURCE_SET_BAY_REQUIRED"):
        export_verified_resolved_integration_bays(
            (replace(candidate, source=ManufacturingSourceIdentity("panel", "sha")),),
            tmp_path / "out", pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("failure", ["verifier", "guard"])
def test_verified_bay_failure_never_commits_unverified_dxf(tmp_path, monkeypatch, failure):
    from pathlib import Path
    from types import SimpleNamespace
    from ae_engine import export_verified_resolved_integration_bays
    from ae_engine import manufacturing_verification

    out = tmp_path / "out"
    out.mkdir()
    existing = out / "SetA__Bay1__door.dxf"
    existing.write_bytes(b"previous-good-DXF")
    events = []
    def writer(render_data, path, *, overwrite):
        Path(path).write_bytes(b"new-but-unverified-DXF")

    def verifier(render_data, path, **kwargs):
        events.append("reopened")
        return SimpleNamespace(ok=failure != "verifier")

    def guard():
        events.append("guard")
        if failure == "guard" and events.count("guard") > 1:
            raise RuntimeError("stale source state")

    monkeypatch.setattr(manufacturing_api, "save_part_render_data_dxf", writer)
    monkeypatch.setattr(manufacturing_verification, "verify_saved_part_render_data_dxf", verifier)
    with pytest.raises((ValueError, RuntimeError)):
        export_verified_resolved_integration_bays(
            (_source_bay(),), out, overwrite=True, pre_commit_guard=guard,
        )
    assert existing.read_bytes() == b"previous-good-DXF"
    assert not list(out.glob(".whd-dxf-stage-*"))
