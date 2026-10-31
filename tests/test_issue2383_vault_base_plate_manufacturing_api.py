# -*- coding: utf-8 -*-
"""#2383: trusted Vault standalone BasePlate W-03 → W-04 → actual DXF reopen.

Only the AE-owned flat BasePlate with independently explicit shrink and bend.
This does NOT certify Receiving-specific plate patterns, NFB parts or joints.
"""
from copy import deepcopy
import hashlib

import ezdxf
import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_api import (
    build_part_render_data, verify_saved_part_render_data_dxf,
)
from integration_cli.prepare_batch import vault_base_plate_spec_from_trusted_prepared_part
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
from tests.test_issue2378_prepare_batch import (
    COMMIT, ENGINE, KEY, _root, _prepare, _request,
    _export_request_from_prepared,
)


def _source_and_request(tmp_path):
    root, _, _ = _root(tmp_path)
    original = tmp_path / "CADSplit-blank-physical-plate.dxf"
    dxf = ezdxf.new("R2010")
    dxf.header["$INSUNITS"] = 4
    dxf.saveas(original)
    assert not list(ezdxf.readfile(original).modelspace())
    request = _request()
    item = request["items"][0]
    item["source_document_sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
    part = item["part"]
    part.clear()
    part.update({
        "kind": "base_plate", "cabinet_family": "金庫型",
        "source_part_ref": "verified-physical-vault-baseplate-001",
        "dimension_semantics": "part_formed_outer",
        "dimensions_mm": {"width": 500.0, "height": 350.0, "thickness": 2.0},
        "shrink_top_mm": 5.0,
        "shrink_bottom_mm": 5.0,
        "shrink_left_mm": 10.0,
        "shrink_right_mm": 10.0,
        "bend_mm": 15.0,
    })
    request["request_digest"] = compute_wire_request_digest(request)
    return root, original, request


def test_vault_base_plate_prepare_to_real_dxf_reopen_uses_canonical_scene(tmp_path):
    root, source, request = _source_and_request(tmp_path)
    prepared = _prepare(request, root)
    frame = prepared["items"][0]["target_frames"][0]
    assert frame["frame_id"].startswith("base_plate:")
    assert frame["allowed_feature_types"] == []
    assert "unfolded Final Material" in frame["origin_definition"]
    assert prepared["items"][0]["required_inputs"] == []
    assert prepared["manufacturing_verified"] is False

    spec = vault_base_plate_spec_from_trusted_prepared_part(request["items"][0]["part"])
    expected = build_part_render_data(spec, ManufacturingContext(resource_root=root))
    assert not expected.material.is_empty and expected.material.is_valid
    min_x, min_y, max_x, max_y = map(float, expected.material.bounds)
    assert frame["finished_face_dimensions_mm"] == {
        "width": max_x - min_x, "height": max_y - min_y,
    }
    export = _export_request_from_prepared(request, prepared)
    output = tmp_path / "real-vault-plate-dxf"
    actual = save_trusted_door_circle_finalscene_batch(
        request, prepared, export,
        source_documents={request["items"][0]["item_id"]: source},
        resource_root=root, output_dir=output,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    physical_id = prepared["items"][0]["physical_part_id"]
    path = output / (physical_id + ".dxf")
    assert actual == {physical_id: str(path)}
    assert path.is_file() and path.stat().st_size > 0
    reopened = ezdxf.readfile(path)
    assert reopened.modelspace().query('*[layer=="CUTTING"]')
    result = verify_saved_part_render_data_dxf(expected, path)
    assert result.ok, result.issues


@pytest.mark.parametrize("invalid", [
    "missing_shrink", "missing_bend", "wrong_family", "cabinet_semantics",
    "missing_thickness", "excess_shrink", "door_override", "nan_shrink",
])
def test_vault_base_plate_rejects_uncertified_source_geometry(tmp_path, invalid):
    root, _, request = _source_and_request(tmp_path)
    p = request["items"][0]["part"]
    if invalid == "missing_shrink":
        del p["shrink_top_mm"]
    elif invalid == "missing_bend":
        del p["bend_mm"]
    elif invalid == "wrong_family":
        p["cabinet_family"] = "受電箱"
    elif invalid == "cabinet_semantics":
        p["dimension_semantics"] = "cabinet_outer"
    elif invalid == "missing_thickness":
        del p["dimensions_mm"]["thickness"]
    elif invalid == "excess_shrink":
        p["shrink_left_mm"] = 600
    elif invalid == "door_override":
        p["frame_edges"] = {"left": True, "right": True, "top": True, "bottom": True}
    elif invalid == "nan_shrink":
        p["shrink_left_mm"] = float("nan")
        # Domain adapter must fail even if callers bypass JSON schema.
        with pytest.raises(PrepareEvidenceError):
            vault_base_plate_spec_from_trusted_prepared_part(p)
        return
    request["request_digest"] = compute_wire_request_digest(request)
    with pytest.raises(Exception):
        _prepare(request, root)
    assert not list((tmp_path / "output").glob("*.dxf")) if (tmp_path / "output").exists() else True


def test_vault_base_plate_detects_source_dxf_geometry_not_transferred(tmp_path):
    root, source, request = _source_and_request(tmp_path)
    dxf = ezdxf.readfile(source)
    dxf.modelspace().add_circle((60, 65), 4, dxfattribs={"layer": "CUTTING"})
    dxf.saveas(source)
    request["items"][0]["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    prepared = _prepare(request, root)
    export = _export_request_from_prepared(request, prepared)
    path = tmp_path / "blocked-untransferred-plate"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request, prepared, export,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=path,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not path.exists()


def test_vault_base_plate_export_rejects_post_prepare_parameter_drift(tmp_path):
    root, source, request = _source_and_request(tmp_path)
    prepared = _prepare(request, root)
    export = _export_request_from_prepared(request, prepared)
    export["items"][0]["part"]["shrink_left_mm"] += 1.0
    export["request_digest"] = compute_wire_request_digest(export)
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request, prepared, export,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=tmp_path / "drifted-output",
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_PREPARE_STALE"
    assert not (tmp_path / "drifted-output").exists()


def test_vault_base_plate_missing_baseline_is_not_a_generic_baseline_bypass(tmp_path):
    from integration_cli.prepare_evidence import build_resource_evidence
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import resolve_policy
    from dataclasses import asdict

    root, _, request = _source_and_request(tmp_path)
    result = _prepare(request, root)
    assert result["status"] == "success"  # installed AE has no BasePlate baseline DXF
    policy = asdict(resolve_policy(ManufacturingContext(resource_root=root)))
    with pytest.raises(PrepareEvidenceError) as exc:
        build_resource_evidence(
            resource_root=root, registry_path="基準檔/截角資料庫/certified_relief_rules.json",
            baseline_paths=[], resolved_policy=policy,
            locked_inputs={"items": [{"locked_dimensions_mm": {
                "raw_part": {"kind": "door", "cabinet_family": "金庫型"}
            }}]}, engine_commit=COMMIT, engine_sha256=ENGINE, build_id="test-only-source",
        )
    assert exc.value.code == "WHD_RESOURCE_UNVERIFIED"
