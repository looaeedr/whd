# -*- coding: utf-8 -*-
"""#2383 Vault integral canonical BoxBody must create actual CUTTING/BEND DXF."""
from copy import deepcopy
import hashlib

import ezdxf
import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_api import (
    build_part_render_data, save_verified_final_scene_batch_dxf,
    verify_saved_part_render_data_dxf,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.worker_box_body import (
    vault_box_body_spec_from_trusted_prepared_part,
    resolve_vault_box_body_size_only_frame,
    require_canonical_vault_box_body_size_only_frame,
)


def _part():
    return {
        "kind": "box_body", "cabinet_family": "金庫型",
        "source_part_ref": "box_body", "dimension_semantics": "cabinet_outer",
        "dimensions_mm": {"width": 400.0, "height": 600.0, "depth": 250.0, "thickness": 2.0},
        "frame_width_mm": 25.0,
        "box_zl1_mm": -15.0, "box_zl2_mm": 20.0,
        "box_zr1_mm": 15.0, "box_zr2_mm": 20.0,
        "box_z_comp_mm": 2.0,
    }


def test_vault_integral_box_body_uses_w_h_d_fold_and_true_dxf(tmp_path):
    spec = vault_box_body_spec_from_trusted_prepared_part(_part())
    assert spec.model_name == "金庫型"
    assert spec.width == 400.0 and spec.depth == 250.0
    assert len(spec.fold_profile) == 9
    assert spec.fold_profile[4].core == "W"
    assert spec.fold_profile[-1].phase6_key == "zr1"
    assert not spec.structure_state

    ctx = ManufacturingContext()
    render = build_part_render_data(spec, ctx)
    assert not render.material.is_empty and render.material.is_valid
    assert render.fold_guides
    physical = "whd-" + hashlib.sha256(b"vault-body").hexdigest()[:24]
    frame = resolve_vault_box_body_size_only_frame(spec, ctx, physical_part_id=physical)
    require_canonical_vault_box_body_size_only_frame(frame, physical_part_id=physical)
    assert frame["allowed_feature_types"] == []
    minx, miny, maxx, maxy = map(float, render.material.bounds)
    assert frame["finished_face_dimensions_mm"] == {
        "width": maxx - minx, "height": maxy - miny,
    }
    out = tmp_path / "independently-verified"
    paths = save_verified_final_scene_batch_dxf(
        [(physical, render)], out, pre_commit_guard=lambda: None,
    )
    dest = out / (physical + ".dxf")
    assert paths == {physical: str(dest)}
    assert dest.is_file() and ezdxf.readfile(dest).modelspace().query('*[layer=="CUTTING"]')
    assert ezdxf.readfile(dest).modelspace().query('*[layer=="BEND"]')
    result = verify_saved_part_render_data_dxf(render, dest)
    assert result.ok, result.issues


@pytest.mark.parametrize("mutation", [
    "missing_profile_input", "receiving", "wrong_semantics", "no_depth",
    "zero_fw", "huge_fw", "zero_w", "missing_t", "negative_height",
    "manual_fold", "door_frame", "fold_axis", "missing_factory_fold",
    "nan_factory", "bool_factory", "extra_dimension",
])
def test_vault_box_body_rejects_noncanonical_physical_inputs(mutation):
    part = _part()
    dims = part["dimensions_mm"]
    if mutation == "missing_profile_input":
        del part["box_zr2_mm"]
    elif mutation == "receiving":
        part["cabinet_family"] = "受電箱"
    elif mutation == "wrong_semantics":
        part["dimension_semantics"] = "part_formed_outer"
    elif mutation == "no_depth":
        del dims["depth"]
    elif mutation == "zero_fw":
        part["frame_width_mm"] = 0
    elif mutation == "huge_fw":
        part["frame_width_mm"] = 999
    elif mutation == "zero_w":
        dims["width"] = 0
    elif mutation == "missing_t":
        del dims["thickness"]
    elif mutation == "negative_height":
        dims["height"] = -100
    elif mutation == "manual_fold":
        part["fold_profile"] = [{"length_mm": 100, "angle_deg": None}]
    elif mutation == "door_frame":
        part["frame_edges"] = {"left": True}
    elif mutation == "fold_axis":
        part["fold_axis"] = "X"
    elif mutation == "missing_factory_fold":
        del part["box_zl1_mm"]
    elif mutation == "nan_factory":
        part["box_zl1_mm"] = float("nan")
    elif mutation == "bool_factory":
        part["box_zr1_mm"] = False
    elif mutation == "extra_dimension":
        dims["unsupported"] = 100
    with pytest.raises(PrepareEvidenceError):
        vault_box_body_spec_from_trusted_prepared_part(part)


def test_vault_box_body_size_only_frame_rejects_external_feature_authorization():
    part = _part()
    spec = vault_box_body_spec_from_trusted_prepared_part(part)
    physical = "whd-" + "d" * 24
    frame = resolve_vault_box_body_size_only_frame(
        spec, ManufacturingContext(), physical_part_id=physical,
    )
    for field, val in (
        ("allowed_feature_types", ["circle"]),
        ("origin_xyz_mm", [50.0, 0.0, 0.0]),
        ("face_role", "front"),
    ):
        forged = deepcopy(frame)
        forged[field] = val
        with pytest.raises(PrepareEvidenceError):
            require_canonical_vault_box_body_size_only_frame(forged, physical_part_id=physical)


def test_vault_integral_box_body_signed_prepare_to_verified_final_dxf(tmp_path):
    from pathlib import Path
    import shutil
    from tests.test_issue2378_prepare_batch import (
        COMMIT, ENGINE, KEY, HERE, _root, _prepare, _request,
        _export_request_from_prepared,
    )
    from integration_cli.request_canonical import compute_wire_request_digest
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
    from ae_engine.manufacturing_api import expected_baseline_path_for

    root, _, _ = _root(tmp_path)
    spec = vault_box_body_spec_from_trusted_prepared_part(_part())
    baseline = expected_baseline_path_for(spec, ManufacturingContext(resource_root=root))
    assert baseline is not None
    baseline = Path(baseline)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "基準檔" / "金庫型" / "箱身.dxf", baseline)
    source = tmp_path / "empty-confirmed-original.dxf"
    dxf = ezdxf.new("R2010")
    dxf.header["$INSUNITS"] = 4
    dxf.saveas(source)
    request = _request()
    request["items"][0]["part"] = _part()
    request["items"][0]["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    prepared = _prepare(request, root)
    frame = prepared["items"][0]["target_frames"][0]
    assert frame["frame_id"].startswith("box_body:")
    assert frame["allowed_feature_types"] == []
    export = _export_request_from_prepared(request, prepared)
    out = tmp_path / "real-vault-boxbody"
    saved = save_trusted_door_circle_finalscene_batch(
        request, prepared, export,
        source_documents={request["items"][0]["item_id"]: source},
        resource_root=root, output_dir=out,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    physical = prepared["items"][0]["physical_part_id"]
    dest = out / (physical + ".dxf")
    assert saved == {physical: str(dest)} and dest.is_file()
    expected = build_part_render_data(spec, ManufacturingContext(resource_root=root))
    verified = verify_saved_part_render_data_dxf(expected, dest)
    assert verified.ok, verified.issues
    reopened = ezdxf.readfile(dest)
    assert reopened.modelspace().query('*[layer=="CUTTING"]')
    assert reopened.modelspace().query('*[layer=="BEND"]')


def test_vault_integral_box_body_rejects_original_source_cutting_before_export(tmp_path):
    from pathlib import Path
    import shutil
    from tests.test_issue2378_prepare_batch import (
        COMMIT, ENGINE, KEY, HERE, _root, _prepare, _request,
        _export_request_from_prepared,
    )
    from integration_cli.request_canonical import compute_wire_request_digest
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
    from ae_engine.manufacturing_api import expected_baseline_path_for

    root, _, _ = _root(tmp_path)
    spec = vault_box_body_spec_from_trusted_prepared_part(_part())
    baseline = Path(expected_baseline_path_for(spec, ManufacturingContext(resource_root=root)))
    baseline.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "基準檔" / "金庫型" / "箱身.dxf", baseline)
    source = tmp_path / "real-source-has-feature.dxf"
    dxf = ezdxf.new("R2010")
    dxf.header["$INSUNITS"] = 4
    dxf.modelspace().add_circle((60, 60), 3, dxfattribs={"layer": "CUTTING"})
    dxf.saveas(source)
    request = _request()
    request["items"][0]["part"] = _part()
    request["items"][0]["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    out = tmp_path / "must-not-write-boxbody"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request, receipt, export,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=out,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED" and not out.exists()
