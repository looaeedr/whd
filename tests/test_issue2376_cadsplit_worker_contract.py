# -*- coding: utf-8 -*-
"""#2376: versioned WHD-owned wire schemas; never assert a Worker exists."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

SCHEMAS = Path(__file__).resolve().parents[1] / "integration_cli" / "schemas"
HASH = "a" * 64
OTHER_HASH = "b" * 64
COMMIT = "c" * 40


def schema(name):
    obj = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(obj)
    return Draft202012Validator(obj)


def prepare():
    return {
        "protocol_version": "1.0.0",
        "client_installation_id": "cadsplit-install-1",
        "request_id": "prepare-001",
        "job_id": "job-001",
        "request_digest": HASH,
        "operation": "prepare",
        "coordinate_contract_revision": "1",
        "items": [{
            "item_id": "task-門一",
            "source_document_sha256": OTHER_HASH,
            "part": {
                "kind": "door",
                "cabinet_family": "金庫型",
                "source_part_ref": "panel/門一",
                "dimension_semantics": "cabinet_outer",
                "dimensions_mm": {
                    "width": 500.0, "height": 600.0, "thickness": 2.0
                }
            }
        }]
    }


def transform():
    return {
        "source_frame_id": "source/dxf-wcs",
        "source_units": "mm",
        "source_to_mm_scale": 1.0,
        "source_dimensions_mm": {"width": 600.0, "height": 500.0},
        "target_dimensions_mm": {"width": 500.0, "height": 600.0},
        "unit_authority": "verified original DXF metadata",
        "matrix_2x2": [[0, -1], [1, 0]],
        "translation_mm": [500.0, 0.0],
        "rotation_deg": 90,
        "mirror_x": False,
        "mirror_y": False,
        "source_geometry_sha256": OTHER_HASH,
        "source_entity_refs": ["source/entity-001"]
    }


def export():
    req = prepare()
    req["operation"] = "export"
    req["request_id"] = "export-001"
    req["transaction_mode"] = "all_or_nothing"
    req["prepare_token"] = "WHD-issued-opaque-prepare-token"
    req["environment_fingerprint_expected"] = HASH
    req["output"] = {"directory": "C:/加工圖", "overwrite": True}
    item = req["items"][0]
    item["preparation_digest"] = HASH
    item["physical_part_id"] = "whd-physical-door-1"
    item["target_frame_ids"] = ["whd-door-1-outer"]
    item["features"] = [{
        "feature_id": "hole-左上",
        "source_ref": "source/entity-001",
        "type": "circle",
        "coordinate_space": "finished_face",
        "target_frame_id": "whd-door-1-outer",
        "units": "mm",
        "face_role": "outer",
        "viewed_from": "along_normal",
        "process": "THROUGH_CUT",
        "source_transform": transform(),
        "center_mm": [100.0, 120.0],
        "radius_mm": 5.0
    }]
    return req


def frame():
    return {
        "frame_id": "whd-door-1-outer",
        "coordinate_contract_revision": "1",
        "units": "mm",
        "origin_definition": "WHD-issued finished-face datum",
        "origin_xyz_mm": [0, 0, 0],
        "axis_x": [1, 0, 0],
        "axis_y": [0, 1, 0],
        "normal": [0, 0, 1],
        "face_role": "outer",
        "viewed_from": "along_normal",
        "finished_face_dimensions_mm": {"width": 500, "height": 600},
        "allowed_feature_types": ["circle", "rect"]
    }


def prepare_response():
    return {
        "protocol_version": "1.0.0",
        "client_installation_id": "cadsplit-install-1",
        "request_id": "prepare-001",
        "job_id": "job-001",
        "request_digest": HASH,
        "operation": "prepare",
        "status": "success",
        "engine_commit": COMMIT,
        "build_id": "test-not-released",
        "environment_fingerprint": HASH,
        "manufacturing_verified": False,
        "prepare_token": "WHD-issued-opaque-prepare-token",
        "items": [{
            "item_id": "task-門一",
            "status": "prepared",
            "physical_part_id": "whd-physical-door-1",
            "preparation_digest": HASH,
            "target_frames": [frame()],
            "manufacturing_verified": False,
            "diagnostics": []
        }],
        "diagnostics": []
    }


def capabilities():
    flags = {
        key: False for key in (
            "batch_prepare", "batch_export", "atomic_batch",
            "internal_verify_on_export", "idempotent_job_submission",
            "output_path_locking", "job_result_readback",
            "per_part_transactions", "cancellation", "crash_recovery"
        )
    }
    return {
        "protocol_version": "1.0.0",
        "operation": "capabilities",
        "installation_id": "whd-test-only",
        "engine_version": "pre-release",
        "engine_commit": COMMIT,
        "build_id": "test-not-released",
        "engine_sha256": HASH,
        "resource_revision": HASH,
        "registry_sha256": HASH,
        "baseline_manifest_sha256": HASH,
        "policy_sha256": HASH,
        "coordinate_contract_revision": "1",
        "min_client_version": "1.0.0",
        "max_batch_items": 20,
        "supported_part_kinds": [],
        "capability_flags": flags,
        "capabilities": [],
        "resource_health": {
            "registry": "missing", "baseline": "missing", "policy": "missing"
        }
    }


def test_all_schema_definitions_are_valid_draft_202012():
    for name in (
        "request_v1.schema.json", "response_v1.schema.json",
        "capabilities_v1.schema.json"
    ):
        schema(name)


def test_prepare_and_export_validate_with_explicit_chinese_source_identity():
    validator = schema("request_v1.schema.json")
    validator.validate(prepare())
    validator.validate(export())
    json.dumps(export(), ensure_ascii=False, allow_nan=False)


@pytest.mark.parametrize("mutation", [
    lambda r: r.pop("client_installation_id"),
    lambda r: r["items"][0].pop("source_document_sha256"),
    lambda r: r["items"][0]["part"].update(kind="unknown"),
    lambda r: r["items"][0]["part"].update(dimension_semantics="guessed"),
    lambda r: r["items"][0]["part"]["dimensions_mm"].update(thickness=-2),
    lambda r: r.update(protocol_version="2.0.0"),
    lambda r: r.update(prepare_token="forbidden on prepare"),
])
def test_prepare_rejects_missing_provenance_and_unsupported_wire_values(mutation):
    request = prepare()
    mutation(request)
    with pytest.raises(ValidationError):
        schema("request_v1.schema.json").validate(request)


@pytest.mark.parametrize("mutation", [
    lambda r: r.pop("prepare_token"),
    lambda r: r.pop("environment_fingerprint_expected"),
    lambda r: r["items"][0].pop("target_frame_ids"),
    lambda r: r["items"][0]["features"][0].pop("source_transform"),
    lambda r: r["items"][0]["features"][0].update(coordinate_space="unfolded"),
    lambda r: r["items"][0]["features"][0].update(units="pixel"),
    lambda r: r["items"][0]["features"][0].update(process="UNKNOWN"),
    lambda r: r["items"][0]["features"][0]["source_transform"].pop("mirror_y"),
    lambda r: r["items"][0]["features"][0]["source_transform"].pop("source_dimensions_mm"),
    lambda r: r["items"][0]["features"][0]["source_transform"].update(source_to_mm_scale=25.4),
    lambda r: r["items"][0]["features"][0]["source_transform"].update(rotation_deg=45),
    lambda r: r["items"][0]["features"][0]["source_transform"].update(source_units="guessed"),
    lambda r: r.update(transaction_mode="unknown"),
])
def test_export_rejects_unverified_frame_or_transport_semantics(mutation):
    request = export()
    mutation(request)
    with pytest.raises(ValidationError):
        schema("request_v1.schema.json").validate(request)


def test_export_with_no_holes_still_requires_prepared_frame_identity():
    request = export()
    request["items"][0]["features"] = []
    schema("request_v1.schema.json").validate(request)
    del request["items"][0]["target_frame_ids"]
    with pytest.raises(ValidationError):
        schema("request_v1.schema.json").validate(request)


def test_prepare_response_is_not_manufacturing_certification():
    validator = schema("response_v1.schema.json")
    validator.validate(prepare_response())
    result = prepare_response()
    result["manufacturing_verified"] = True
    with pytest.raises(ValidationError):
        validator.validate(result)


def test_successful_export_must_attest_each_committed_physical_part():
    result = prepare_response()
    result.pop("prepare_token")
    result["operation"] = "export"
    result["request_id"] = "export-001"
    result["transaction_mode"] = "all_or_nothing"
    result["manufacturing_verified"] = True
    item = result["items"][0]
    item.pop("target_frames")
    item.pop("preparation_digest")
    item["status"] = "committed"
    item["manufacturing_verified"] = True
    item["production_scope"] = "single_part"
    item["parts"] = [{
        "physical_part_id": "whd-physical-door-1",
        "part_kind": "door",
        "output_path": "C:/加工圖/門一.dxf",
        "output_sha256": HASH,
        "save_reload_verified": True,
        "manufacturing_verified": True,
        "exporter_name": "WHD-owned exporter",
        "used_baseline": False
    }]
    validator = schema("response_v1.schema.json")
    validator.validate(result)
    item["parts"][0]["save_reload_verified"] = False
    with pytest.raises(ValidationError):
        validator.validate(result)


def test_partial_result_only_with_per_part_transaction():
    result = prepare_response()
    result["status"] = "partial"
    result["operation"] = "export"
    result["transaction_mode"] = "all_or_nothing"
    with pytest.raises(ValidationError):
        schema("response_v1.schema.json").validate(result)


def test_capabilities_are_attestation_not_fake_production_support():
    validator = schema("capabilities_v1.schema.json")
    validator.validate(capabilities())
    result = capabilities()
    result["capability_flags"].pop("output_path_locking")
    with pytest.raises(ValidationError):
        validator.validate(result)


def test_explicit_inch_source_requires_correct_conversion_and_provenance():
    request = export()
    tx = request["items"][0]["features"][0]["source_transform"]
    tx["source_units"] = "inch"
    tx["source_to_mm_scale"] = 25.4
    tx["unit_authority"] = "confirmed source drawing units"
    schema("request_v1.schema.json").validate(request)
    tx["source_to_mm_scale"] = 1.0
    with pytest.raises(ValidationError):
        schema("request_v1.schema.json").validate(request)


def test_malformed_request_can_receive_structured_failure_without_unknown_job_id():
    result = {
        "protocol_version": "1.0.0",
        "operation": "prepare",
        "status": "failed",
        "engine_commit": COMMIT,
        "build_id": "test-not-released",
        "manufacturing_verified": False,
        "items": [],
        "diagnostics": [{
            "code": "WHD_PROTOCOL_INCOMPATIBLE",
            "message": "無法解析來源 request_id / job_id",
            "retryable": False
        }]
    }
    validator = schema("response_v1.schema.json")
    validator.validate(result)
    result["manufacturing_verified"] = True
    with pytest.raises(ValidationError):
        validator.validate(result)


def test_successful_response_cannot_omit_job_correlation():
    result = prepare_response()
    result.pop("request_digest")
    with pytest.raises(ValidationError):
        schema("response_v1.schema.json").validate(result)
