# -*- coding: utf-8 -*-
"""#2378 integrated WHD Door-local prepare. No DXF or public CLI activation."""
from copy import deepcopy
from pathlib import Path
import shutil

import ezdxf

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


# W-03 extra scope: export-time recheck of Worker-owned prepare state.
def _export_request_from_prepared(prepare_request, receipt):
    export = {
        "protocol_version": "1.1.0",
        "client_installation_id": prepare_request["client_installation_id"],
        "request_id": "export-wire-001",
        "job_id": prepare_request["job_id"],
        "request_digest": "a"*64,
        "operation": "export",
        "coordinate_contract_revision": "1",
        "prepare_token": receipt["prepare_token"],
        "environment_fingerprint_expected": receipt["environment_fingerprint"],
        "transaction_mode": "all_or_nothing",
        "output": {"directory": "worker-output-not-created", "overwrite": False},
        "items": [{
            **deepcopy(prepared),
            "physical_part_id": registered["physical_part_id"],
            "preparation_digest": registered["preparation_digest"],
            "target_frame_ids": [f["frame_id"] for f in registered["target_frames"]],
            "features": [],
        } for prepared, registered in zip(prepare_request["items"], receipt["items"])],
    }
    export["request_digest"] = compute_wire_request_digest(export)
    return export


def _recheck(original, receipt, export, root, **overrides):
    from integration_cli.prepare_recheck import recheck_trusted_door_export
    kwargs = {
        "resource_root": root, "engine_commit": COMMIT,
        "engine_sha256": ENGINE, "build_id": "test-only-source",
        "worker_key": KEY,
    }
    kwargs.update(overrides)
    recheck_trusted_door_export(original, receipt, export, **kwargs)


def test_export_precommit_recheck_is_read_only_and_transport_retry_is_safe(tmp_path):
    root, _, _ = _root(tmp_path)
    original = _request(count=2)
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    _recheck(original, receipt, export, root)
    retried = deepcopy(export)
    retried["request_id"] = "reissued-correlation-after-timeout"
    # Only request_id is transport-only; digest remains unchanged.
    _recheck(original, receipt, retried, root)
    changed_output = deepcopy(export)
    changed_output["output"]["directory"] = "another-trusted-export-dir"
    changed_output["request_digest"] = compute_wire_request_digest(changed_output)
    _recheck(original, receipt, changed_output, root)
    assert not (tmp_path / "worker-output-not-created").exists()


@pytest.mark.parametrize("tamper", [
    "job", "client", "part_size", "source_sha", "source_part", "order",
    "physical", "prep_digest", "frame_id", "env", "token",
    "prepared_receipt_token", "prepared_request_digest", "source_transform_role",
])
def test_export_recheck_rejects_semantic_mutation_entire_batch(tmp_path, tamper):
    root, _, _ = _root(tmp_path)
    original = _request(count=2)
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    if tamper == "job":
        export["job_id"] = "different-job"
    elif tamper == "client":
        export["client_installation_id"] = "DIFFERENT-CLIENT"
    elif tamper == "part_size":
        export["items"][0]["part"]["dimensions_mm"]["width"] = 601
    elif tamper == "source_sha":
        export["items"][0]["source_document_sha256"] = "a"*64
    elif tamper == "source_part":
        export["items"][0]["part"]["source_part_ref"] = "changed-reference"
    elif tamper == "order":
        export["items"].reverse()
    elif tamper == "physical":
        export["items"][0]["physical_part_id"] = "other-physical"
    elif tamper == "prep_digest":
        export["items"][0]["preparation_digest"] = "a"*64
    elif tamper == "frame_id":
        export["items"][0]["target_frame_ids"] = ["door:spoof:front:local-v1"]
    elif tamper == "env":
        export["environment_fingerprint_expected"] = "d"*64
    elif tamper == "token":
        export["prepare_token"] = "w3." + "a"*64 + "." + "a"*64
    elif tamper == "prepared_receipt_token":
        receipt["prepare_token"] = "w3." + "b"*64 + "." + "b"*64
    elif tamper == "prepared_request_digest":
        original["request_digest"] = "d"*64
    elif tamper == "source_transform_role":
        f = receipt["items"][0]["target_frames"][0]
        export["items"][0]["features"] = [{
            "feature_id": "hole-1",
            "source_ref": "src-circle-1",
            "type": "circle",
            "coordinate_space": "finished_face",
            "target_frame_id": f["frame_id"],
            "units": "mm", "face_role": "back",
            "viewed_from": "along_normal",
            "process": "THROUGH_CUT",
            "center_mm": [20, 20], "radius_mm": 3,
            "source_transform": {
                "source_frame_id": "CAD-ORIGIN",
                "source_units": "mm", "source_to_mm_scale": 1,
                "unit_authority": "DXF-HEADER", "matrix_2x2": [[1,0],[0,1]],
                "translation_mm": [0,0], "rotation_deg": 0,
                "mirror_x": False, "mirror_y": False,
                "source_geometry_sha256": "f"*64, "source_entity_refs": ["entity-1"],
                "source_dimensions_mm": {"width": 500, "height": 600},
                "target_dimensions_mm": dict(f["finished_face_dimensions_mm"]),
            },
        }]
    if tamper != "prepared_request_digest":
        export["request_digest"] = compute_wire_request_digest(export)
    with pytest.raises(PrepareEvidenceError) as exc:
        _recheck(original, receipt, export, root)
    assert exc.value.code in {"WHD_PREPARE_STALE", "WHD_REQUEST_DIGEST_MISMATCH"}


@pytest.mark.parametrize("change", ["registry", "baseline", "engine", "build", "key", "factory_policy"])
def test_export_recheck_rejects_changed_actual_environment(tmp_path, monkeypatch, change):
    root, registry, baseline = _root(tmp_path)
    original = _request()
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    overrides = {}
    if change == "registry":
        registry.write_text(registry.read_text(encoding="utf-8")+"\\n", encoding="utf-8")
    elif change == "baseline":
        doc = ezdxf.readfile(baseline)
        doc.modelspace().add_line((0,0),(1,1),dxfattribs={"layer":"MARKING"})
        doc.saveas(baseline)
    elif change == "engine":
        overrides["engine_sha256"] = "e"*64
    elif change == "build":
        overrides["build_id"] = "new-worker-build"
    elif change == "key":
        overrides["worker_key"] = b"different-trusted-key-" + b"z"*32
    elif change == "factory_policy":
        from ae_engine import ae
        monkeypatch.setattr(ae, "door_gap_w_def", float(ae.door_gap_w_def)+0.5)
    with pytest.raises(PrepareEvidenceError) as exc:
        _recheck(original, receipt, export, root, **overrides)
    assert exc.value.code == "WHD_PREPARE_STALE"
