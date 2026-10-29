# -*- coding: utf-8 -*-
"""#2378 integrated WHD Door-local prepare. No DXF or public CLI activation."""
from copy import deepcopy
from pathlib import Path
import shutil

import ezdxf

import pytest
from jsonschema import Draft202012Validator

from integration_cli.prepare_batch import prepare_trusted_door_batch
from integration_cli.prepare_revalidation import revalidate_trusted_door_preparation
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest

HERE = Path(__file__).resolve().parents[1]
KEY = b"trusted-owned-WHD-install-secret-" + b"x" * 32
COMMIT = "c" * 40
ENGINE = "d" * 64


def _request(*, count=1):
    request = {
        "protocol_version":"1.1.0",
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
    shutil.copy2(HERE/"基準檔"/"截角資料庫"/"certified_relief_rules.json", registry)
    model = DoorPartSpec(width=500,height=600,thickness=2,frame_width=25,
                         model_name="金庫型")
    expected=expected_baseline_path_for(model, ManufacturingContext(resource_root=root))
    assert expected is not None, "WHD must resolve a Door baseline path"
    path=Path(expected)
    assert path.is_relative_to(root), "baseline must be rooted in WHD resource root"
    path.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(HERE/"基準檔"/"金庫型"/"門.dxf", path)
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
        HERE/"integration_cli/schemas/response_v1_1.schema.json"
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
    doc=ezdxf.readfile(baseline)
    doc.modelspace().add_line((0,0),(1,1),dxfattribs={"layer":"MARKING"})
    doc.saveas(baseline)
    assert _prepare(request,root)["prepare_token"]!=first["prepare_token"]
    shutil.copy2(HERE/"基準檔"/"金庫型"/"門.dxf", baseline)
    registry.write_text(registry.read_text(encoding="utf-8")+"\n",encoding="utf-8")
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


def test_registry_hash_alone_does_not_certify_synthetic_registry(tmp_path):
    root,registry,_=_root(tmp_path)
    registry.write_text('{"synthetic_registry":"not certified"}', encoding="utf-8")
    with pytest.raises(PrepareEvidenceError) as exc:
        _prepare(_request(),root)
    assert exc.value.code=="WHD_RESOURCE_UNVERIFIED"


def test_baseline_hash_alone_does_not_certify_synthetic_dxf(tmp_path):
    root,_,baseline=_root(tmp_path)
    baseline.write_bytes(b"arbitrary nonempty bytes that are not DXF")
    with pytest.raises(PrepareEvidenceError) as exc:
        _prepare(_request(),root)
    assert exc.value.code=="WHD_RESOURCE_UNVERIFIED"


def test_registry_duplicate_active_revision_fails_closed(tmp_path):
    import json
    root,registry,_=_root(tmp_path)
    data=json.loads(registry.read_text(encoding="utf-8"))
    data["rules"].append(dict(data["rules"][0]))
    registry.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
    with pytest.raises(PrepareEvidenceError) as exc:
        _prepare(_request(),root)
    assert exc.value.code=="WHD_RESOURCE_UNVERIFIED"


def test_baseline_has_to_own_real_cutting_geometry(tmp_path):
    root,_,baseline=_root(tmp_path)
    blank=ezdxf.new()
    blank.modelspace().add_line((0,0),(50,50),dxfattribs={"layer":"MARKING"})
    blank.saveas(baseline)
    with pytest.raises(PrepareEvidenceError) as exc:
        _prepare(_request(),root)
    assert exc.value.code=="WHD_RESOURCE_UNVERIFIED"


def _revalidate(request, receipt, root, **overrides):
    arguments = dict(
        prepare_request=request, prepared_receipt=receipt, resource_root=root,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    arguments.update(overrides)
    return revalidate_trusted_door_preparation(**arguments)


def test_revalidate_prepare_receipt_allows_transport_only_retry(tmp_path):
    root,_,_=_root(tmp_path)
    original=_request(count=2)
    receipt=_prepare(original,root)
    assert _revalidate(original,receipt,root) is None
    retry=deepcopy(original)
    retry["request_id"]="another-wire-transaction"
    assert _revalidate(retry,receipt,root) is None
    assert not any("output" in p.name for p in tmp_path.rglob("*.dxf"))


@pytest.mark.parametrize("change", [
    "registry_bytes", "baseline_bytes", "missing_registry", "input_width",
    "source_sha", "engine_sha", "worker_key", "build_id", "forged_token",
    "forged_frame", "forged_physical_id", "forged_status", "extra_field",
])
def test_revalidate_prepare_receipt_rejects_changes_before_export(tmp_path,change):
    root,registry,baseline=_root(tmp_path)
    request=_request(count=2)
    receipt=_prepare(request,root)
    original_token=receipt["prepare_token"]
    request=deepcopy(request)
    receipt=deepcopy(receipt)
    overrides={}
    if change=="registry_bytes":
        registry.write_text(registry.read_text(encoding="utf-8")+"\n",encoding="utf-8")
    elif change=="baseline_bytes":
        document=ezdxf.readfile(baseline)
        document.modelspace().add_line((0,0),(1,1),dxfattribs={"layer":"MARKING"})
        document.saveas(baseline)
    elif change=="missing_registry":
        registry.unlink()
    elif change=="input_width":
        request["items"][0]["part"]["dimensions_mm"]["width"]=501.0
        request["request_digest"]=compute_wire_request_digest(request)
    elif change=="source_sha":
        request["items"][0]["source_document_sha256"]="e"*64
        request["request_digest"]=compute_wire_request_digest(request)
    elif change=="engine_sha":
        overrides["engine_sha256"]="e"*64
    elif change=="worker_key":
        overrides["worker_key"]=b"different-trusted-install-key-" + b"y"*32
    elif change=="build_id":
        overrides["build_id"]="different-build"
    elif change=="forged_token":
        receipt["prepare_token"]="w3."+"a"*64+"."+"b"*64
    elif change=="forged_frame":
        receipt["items"][0]["target_frames"][0]["normal"]=[0,0,-1]
    elif change=="forged_physical_id":
        receipt["items"][0]["physical_part_id"]="whd-synthetic"
    elif change=="forged_status":
        receipt["manufacturing_verified"]=True
    elif change=="extra_field":
        receipt["unrecognized"]="bad"
    with pytest.raises(PrepareEvidenceError) as exc:
        _revalidate(request,receipt,root,**overrides)
    assert exc.value.code=="WHD_PREPARE_STALE"
    assert receipt["prepare_token"]==original_token or change=="forged_token"
    assert not any("output" in p.name for p in tmp_path.rglob("*.dxf"))
