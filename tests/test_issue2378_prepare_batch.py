# -*- coding: utf-8 -*-
"""#2378 integrated WHD Door-local prepare. No DXF or public CLI activation."""
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from integration_cli.prepare_batch import prepare_trusted_door_batch
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest

HERE = Path(__file__).resolve().parents[1]
KEY = b"trusted-owned-WHD-install-secret-" + b"x" * 32
COMMIT = "c" * 40
ENGINE = "d" * 64


def _request(*, count=1):
    request = {
        "protocol_version":"1.0.0",
        "client_installation_id":"CAD-owned-01",
        "request_id":"wire-001",
        "job_id":"job-001",
        "request_digest":"a"*64,
        "operation":"prepare",
        "coordinate_contract_revision":"1",
        "items":[{
            "item_id":f"門片-{i}",
            "source_document_sha256":"f"*64,
            "part":{
                "kind":"door",
                "cabinet_family":"金庫型",
                "source_part_ref":f"verified-source-door-{i}",
                "dimension_semantics":"cabinet_outer",
                "dimensions_mm":{"width":500.0,"height":600.0,"thickness":2.0},
                "frame_edges":{"left":True,"right":True,"top":True,"bottom":True},
            },
        } for i in range(count)],
    }
    request["request_digest"]=compute_wire_request_digest(request)
    return request


def _root(tmp_path):
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import expected_baseline_path_for
    root=tmp_path/"資源 root"
    registry=root/"基準檔"/"截角資料庫"/"certified_relief_rules.json"
    registry.parent.mkdir(parents=True,exist_ok=True)
    registry.write_text('{"synthetic_registry":"only hash receipt test"}',encoding="utf-8")
    model = DoorPartSpec(width=500,height=600,thickness=2,frame_width=25,
                         model_name="金庫型")
    expected=expected_baseline_path_for(model, ManufacturingContext(resource_root=root))
    assert expected is not None, "WHD must resolve a Door baseline path"
    path=Path(expected)
    assert path.is_relative_to(root), "baseline must be rooted in WHD resource root"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b"test-only-DXF-baseline-content")
    return root,registry,path


def _prepare(request,root):
    return prepare_trusted_door_batch(
        request,resource_root=root,engine_commit=COMMIT,
        engine_sha256=ENGINE,build_id="test-only-source",
        worker_key=KEY,
    )


def test_prepares_two_doors_same_process_with_true_canonical_size_and_local_frame(tmp_path):
    root,_,_=_root(tmp_path)
    request=_request(count=2)
    result=_prepare(request,root)
    Draft202012Validator(__import__("json").loads((
        HERE/"integration_cli/schemas/response_v1.schema.json"
    ).read_text(encoding="utf-8"))).validate(result)
    assert result["status"]=="success"
    assert result["manufacturing_verified"] is False
    assert len(result["items"])==2
    assert result["items"][0]["physical_part_id"]!=result["items"][1]["physical_part_id"]
    assert result["items"][0]["preparation_digest"]!=result["items"][1]["preparation_digest"]
    assert all(row["target_frames"][0]["face_role"]=="front" for row in result["items"])
    assert "NOT cabinet-world" in result["items"][0]["target_frames"][0]["origin_definition"]
    assert all(row["status"]=="prepared" for row in result["items"])
    assert not list(tmp_path.rglob("*.dxf")) or not any("output" in p.name for p in tmp_path.rglob("*.dxf"))
    retry=deepcopy(request)
    retry["request_id"]="retry-999"
    assert _prepare(retry,root)["prepare_token"]==result["prepare_token"]
    assert _prepare(retry,root)["environment_fingerprint"]==result["environment_fingerprint"]


def test_prepare_token_fails_closed_after_baseline_or_locked_input_change(tmp_path):
    root,registry,baseline=_root(tmp_path)
    request=_request()
    first=_prepare(request,root)
    baseline.write_bytes(b"changed baseline bytes")
    assert _prepare(request,root)["prepare_token"]!=first["prepare_token"]
    baseline.write_bytes(b"test-only-DXF-baseline-content")
    registry.write_text('{"changed":"registry"}',encoding="utf-8")
    assert _prepare(request,root)["prepare_token"]!=first["prepare_token"]
    request["items"][0]["part"]["dimensions_mm"]["width"]=499
    request["request_digest"]=compute_wire_request_digest(request)
    assert _prepare(request,root)["prepare_token"]!=first["prepare_token"]


def test_reject_invalid_source_frame_edges_and_wrong_semantics(tmp_path):
    root,_,_=_root(tmp_path)
    req=_request()
    del req["items"][0]["part"]["frame_edges"]
    req["request_digest"]=compute_wire_request_digest(req)
    with pytest.raises(PrepareEvidenceError) as exc:
        _prepare(req,root)
    assert exc.value.code=="WHD_FRAME_UNVERIFIED"
    req=_request()
    req["items"][0]["part"]["dimension_semantics"]="part_formed_outer"
    req["request_digest"]=compute_wire_request_digest(req)
    with pytest.raises(PrepareEvidenceError) as exc:
        _prepare(req,root)
    assert exc.value.code=="WHD_FRAME_UNVERIFIED"
    req=_request()
    req["items"][0]["part"]["frame_edges"]["left"]="yes"
    req["request_digest"]=compute_wire_request_digest(req)
    with pytest.raises(Exception):
        _prepare(req,root)


def test_reject_tampered_digest_or_missing_registry(tmp_path):
    root,registry,_=_root(tmp_path)
    req=_request()
    req["items"][0]["part"]["dimensions_mm"]["width"]=501.0
    with pytest.raises(PrepareEvidenceError) as exc:
        _prepare(req,root)
    assert exc.value.code=="WHD_REQUEST_DIGEST_MISMATCH"
    registry.unlink()
    req=_request()
    with pytest.raises(PrepareEvidenceError) as exc:
        _prepare(req,root)
    assert exc.value.code=="WHD_RESOURCE_UNVERIFIED"
