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
    "receipt_manufacturing_flag", "receipt_production_scope", "receipt_required_inputs",
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
    elif tamper == "receipt_manufacturing_flag":
        receipt["items"][0]["manufacturing_verified"] = True
    elif tamper == "receipt_production_scope":
        receipt["items"][0]["production_scope"] = "complete_assembly"
    elif tamper == "receipt_required_inputs":
        receipt["items"][0]["required_inputs"] = ["source_transform"]
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
        registry.write_text(registry.read_text(encoding="utf-8")+"\n", encoding="utf-8")
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


@pytest.mark.parametrize("broken", [
    "registry_deleted", "baseline_deleted", "registry_corrupt", "baseline_corrupt",
])
def test_export_recheck_missing_or_unparseable_source_is_stale(tmp_path, broken):
    root, registry, baseline = _root(tmp_path)
    request = _request()
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    if broken == "registry_deleted":
        registry.unlink()
    elif broken == "baseline_deleted":
        baseline.unlink()
    elif broken == "registry_corrupt":
        registry.write_text('{"not_a_certified_registry": true}', encoding="utf-8")
    else:
        baseline.write_bytes(b"not a valid DXF")
    with pytest.raises(PrepareEvidenceError) as exc:
        _recheck(request, receipt, export, root)
    assert exc.value.code == "WHD_PREPARE_STALE"
    assert not (tmp_path / "worker-output-not-created").exists()


def _indicator_small_door_request(tmp_path, *, groups=(2, 1)):
    """Use WHD's shared small-door owner, not hand-written frame dimensions."""
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import (
        expected_baseline_path_for, indicator_small_door_finished_size,
        indicator_small_door_spec, resolve_policy,
    )

    root, registry, door_baseline = _root(tmp_path)
    # WHD's shared indicator resolver requires both physical baselines in
    # the same owned folder; copying only 小門.dxf would be an invalid resource
    # fixture even if that single DXF parses.
    shared = root / "基準檔" / "指示燈"
    shared.mkdir(parents=True, exist_ok=True)
    for filename in ("盒子.dxf", "小門.dxf"):
        shutil.copy2(HERE / "基準檔" / "指示燈" / filename, shared / filename)
    context = ManufacturingContext(resource_root=root)
    spec = indicator_small_door_spec(groups, thickness=2.0, context=context)
    baseline = expected_baseline_path_for(spec, context)
    assert baseline is not None
    baseline = Path(baseline)
    assert baseline.is_relative_to(root)
    assert baseline == shared / "小門.dxf"

    width, height = indicator_small_door_finished_size(
        groups, thickness=2.0, context=context,
    )
    request = _request()
    part = request["items"][0]["part"]
    part["kind"] = "indicator_small_door"
    part["dimension_semantics"] = "part_formed_outer"
    part["dimensions_mm"] = {"width": width, "height": height, "thickness": 2.0}
    part["indicator_groups"] = list(groups)
    del part["frame_edges"]
    request["request_digest"] = compute_wire_request_digest(request)
    return root, baseline, request, spec


def test_indicator_small_door_uses_whd_shared_baseline_and_canonical_local_frame(tmp_path):
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import door_finished_face_size

    root, baseline, request, spec = _indicator_small_door_request(tmp_path)
    response = _prepare(request, root)
    Draft202012Validator(__import__("json").loads((
        HERE / "integration_cli/schemas/response_v1_1.schema.json"
    ).read_text(encoding="utf-8"))).validate(response)
    assert response["status"] == "success"
    assert response["manufacturing_verified"] is False
    frame = response["items"][0]["target_frames"][0]
    width, height = door_finished_face_size(spec, ManufacturingContext(resource_root=root))
    assert frame["finished_face_dimensions_mm"] == {"width": width, "height": height}
    assert frame["face_role"] == "front"
    assert frame["axis_x"] == [1.0, 0.0, 0.0]
    assert frame["axis_y"] == [0.0, 1.0, 0.0]
    assert response["items"][0]["production_scope"] == "single_part"
    assert baseline.exists()
    retry = deepcopy(request)
    retry["request_id"] = "safe-transport-retry"
    assert _prepare(retry, root)["prepare_token"] == response["prepare_token"]
    exported = _export_request_from_prepared(request, response)
    _recheck(request, response, exported, root)
    baseline.write_bytes(baseline.read_bytes() + b"\n999\nWHD-stale")
    with pytest.raises(PrepareEvidenceError) as exc:
        _recheck(request, response, exported, root)
    assert exc.value.code == "WHD_PREPARE_STALE"


@pytest.mark.parametrize("fault", [
    "wrong_width", "wrong_height", "wrong_semantics",
    "explicit_frame_edges", "explicit_frame_width", "explicit_gap",
    "missing_groups", "invalid_groups", "extra_depth",
])
def test_indicator_small_door_source_claims_fail_closed_without_token(tmp_path, fault):
    root, _, request, spec = _indicator_small_door_request(tmp_path)
    part = request["items"][0]["part"]
    dimensions = part["dimensions_mm"]
    if fault == "wrong_width":
        dimensions["width"] += 1.0
    elif fault == "wrong_height":
        dimensions["height"] += 1.0
    elif fault == "wrong_semantics":
        part["dimension_semantics"] = "cabinet_outer"
    elif fault == "explicit_frame_edges":
        part["frame_edges"] = {key: True for key in ("left", "right", "top", "bottom")}
    elif fault == "explicit_frame_width":
        part["frame_width_mm"] = 99.0
    elif fault == "explicit_gap":
        part["gap_w_mm"] = 4.0
    elif fault == "missing_groups":
        del part["indicator_groups"]
    elif fault == "invalid_groups":
        part["indicator_groups"] = [0]
    elif fault == "extra_depth":
        dimensions["depth"] = 100.0
    request["request_digest"] = compute_wire_request_digest(request)
    if fault == "invalid_groups":
        # Draft wire schema rejects zero groups *before* WHD runtime gets it.
        from jsonschema import ValidationError
        with pytest.raises(ValidationError):
            _prepare(request, root)
    else:
        with pytest.raises(PrepareEvidenceError) as exc:
            _prepare(request, root)
        assert exc.value.code in ("WHD_FRAME_UNVERIFIED", "WHD_PREPARE_INPUT_INVALID")


@pytest.mark.parametrize("kind", ["indicator_box", "end_cap_head", "end_cap_tail"])
def test_unverified_non_door_frames_do_not_issue_prepare_tokens(tmp_path, kind):
    root, _, _ = _root(tmp_path)
    req = _request()
    part = req["items"][0]["part"]
    part["kind"] = kind
    # Cross the wire schema first, then prove the runtime refuses the kind.
    if kind == "indicator_box":
        part["indicator_groups"] = [1]
    else:
        part["dimensions_mm"]["depth"] = 300.0
    req["request_digest"] = compute_wire_request_digest(req)
    with pytest.raises(PrepareEvidenceError) as exc:
        _prepare(req, root)
    assert exc.value.code == "WHD_FRAME_UNVERIFIED"


def test_indicator_small_door_seals_groups_and_rejects_export_replay_mutation(tmp_path):
    root, _, req, _ = _indicator_small_door_request(tmp_path)
    receipt = _prepare(req, root)
    export = _export_request_from_prepared(req, receipt)
    changed = deepcopy(export)
    changed["items"][0]["part"]["indicator_groups"] = [1, 1]
    changed["request_digest"] = compute_wire_request_digest(changed)
    with pytest.raises(PrepareEvidenceError) as exc:
        _recheck(req, receipt, changed, root)
    assert exc.value.code == "WHD_PREPARE_STALE"


def _twenty_mixed_door_small_door_prepare(tmp_path):
    """Twenty distinct physical part identities, both already verified W-03 kinds."""
    root, small_baseline, small, _ = _indicator_small_door_request(tmp_path)
    original = _request(count=20)
    for i, row in enumerate(original["items"]):
        if i % 2:
            part = deepcopy(small["items"][0]["part"])
            part["source_part_ref"] = f"verified-source-small-door-{i}"
            row["part"] = part
    original["request_digest"] = compute_wire_request_digest(original)
    return root, small_baseline, original


def test_twenty_mixed_door_and_small_door_frames_are_separately_sealed(tmp_path):
    """Only in-process prepare/recheck; this is not 20-piece mixed manufacturing."""
    root, _, original = _twenty_mixed_door_small_door_prepare(tmp_path)
    receipt = _prepare(original, root)
    assert receipt["status"] == "success"
    assert receipt["manufacturing_verified"] is False
    items = receipt["items"]
    assert len(items) == 20
    assert len({r["physical_part_id"] for r in items}) == 20
    assert len({r["preparation_digest"] for r in items}) == 20
    assert len({r["target_frames"][0]["frame_id"] for r in items}) == 20
    for i, row in enumerate(items):
        frame = row["target_frames"][0]
        assert row["status"] == "prepared"
        assert row["production_scope"] == "single_part"
        assert frame["face_role"] == "front"
        assert frame["viewed_from"] == "along_normal"
        assert frame["units"] == "mm"
        assert frame["normal"] == [0.0, 0.0, 1.0]
        assert frame["frame_id"].startswith("door:whd-")
    retry = deepcopy(original)
    retry["request_id"] = "retry-transport-only"
    second = _prepare(retry, root)
    assert second["prepare_token"] == receipt["prepare_token"]
    assert [x["preparation_digest"] for x in second["items"]] == [
        x["preparation_digest"] for x in items
    ]
    export = _export_request_from_prepared(original, receipt)
    _recheck(original, receipt, export, root)
    assert not (tmp_path / "worker-output-not-created").exists()


@pytest.mark.parametrize("change", [
    "one_small_door_width",
    "one_small_door_groups",
    "one_door_dimensions",
    "mixed_source_reference",
    "shared_small_door_baseline",
])
def test_twenty_mixed_prepare_one_invalid_item_or_resource_refuses_all(
    tmp_path, change,
):
    root, baseline, original = _twenty_mixed_door_small_door_prepare(tmp_path)
    if change in ("one_small_door_width", "one_door_dimensions"):
        bad = deepcopy(original)
        index = 1 if change == "one_small_door_width" else 0
        bad["items"][index]["part"]["dimensions_mm"]["width"] += 1.0
        bad["request_digest"] = compute_wire_request_digest(bad)
        if change == "one_small_door_width":
            with pytest.raises(PrepareEvidenceError) as exc:
                _prepare(bad, root)
            assert exc.value.code == "WHD_FRAME_UNVERIFIED"
            assert not (tmp_path / "worker-output-not-created").exists()
            return
        # Door source is valid with the changed size, but an exported change
        # to previously prepared part dimensions cannot replace the token.
    receipt = _prepare(original, root)
    export = _export_request_from_prepared(original, receipt)
    if change == "one_door_dimensions":
        export["items"][0]["part"]["dimensions_mm"]["width"] += 1.0
    elif change == "one_small_door_groups":
        export["items"][1]["part"]["indicator_groups"] = [1, 1]
    elif change == "mixed_source_reference":
        export["items"][19]["part"]["source_part_ref"] = "another-source"
    elif change == "shared_small_door_baseline":
        baseline.write_bytes(baseline.read_bytes() + b"\n999\nWHD-stale-mixed")
    export["request_digest"] = compute_wire_request_digest(export)
    with pytest.raises(PrepareEvidenceError) as exc:
        _recheck(original, receipt, export, root)
    assert exc.value.code == "WHD_PREPARE_STALE"
    assert not (tmp_path / "worker-output-not-created").exists()
