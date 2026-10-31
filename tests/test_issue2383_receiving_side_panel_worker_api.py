# -*- coding: utf-8 -*-
"""#2383 Receiving left/right physical side Panel real source DXF→Worker route."""
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil

import ezdxf
import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_api import (
    save_verified_final_scene_batch_dxf, verify_saved_part_render_data_dxf,
)
from integration_cli.worker_receiving_side_panel import (
    receiving_side_panel_spec_from_trusted_part,
    receiving_side_panel_expected_baselines,
    receiving_side_panel_render,
    receiving_side_panel_frame,
    require_receiving_side_panel_frame,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from tests.test_issue2378_prepare_batch import (
    COMMIT, ENGINE, KEY, HERE, _root, _prepare, _request,
    _export_request_from_prepared,
)


def _part(role="left_side"):
    return {
        "kind": "side_panel", "cabinet_family": "受電箱",
        "source_part_ref": f"box_body:{role}",
        "dimension_semantics": "cabinet_outer",
        "dimensions_mm": {
            "width": 800.0, "height": 1600.0,
            "depth": 350.0, "thickness": 2.0,
        },
        "frame_width_mm": 29.0,
        "box_zl1_mm": -24.0, "box_zl2_mm": 24.0,
        "box_zr1_mm": 15.0, "box_zr2_mm": 18.0,
        "box_z_comp_mm": 2.0,
    }


def _root_with_receiving_baselines(tmp_path):
    root, registry, _ = _root(tmp_path)
    for baseline in receiving_side_panel_expected_baselines(root):
        baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / "基準檔" / "受電箱" / baseline.name, baseline)
    return root, registry


@pytest.mark.parametrize("role", ("left_side", "right_side"))
def test_receiving_real_side_geometry_has_its_own_fixed_holes_and_bends(tmp_path, role):
    root, _ = _root_with_receiving_baselines(tmp_path)
    spec, resolved_role = receiving_side_panel_spec_from_trusted_part(_part(role))
    assert resolved_role == role
    assert spec.model_name == "受電箱"
    assert len(spec.fold_profile) == 9
    ctx = ManufacturingContext(resource_root=root)
    render = receiving_side_panel_render(spec, role, ctx)
    assert render.material.is_valid and render.material.area > 0
    assert render.fold_guides
    assert render.metadata["baseline_source_status"] == "VERIFIED"
    assert render.metadata["baseline_feature_count"] == 9
    assert Path(render.metadata["baseline_source_path"]).name == (
        "左側板.dxf" if role == "left_side" else "右側板.dxf"
    )
    physical = "whd-" + hashlib.sha256(role.encode()).hexdigest()[:24]
    frame = receiving_side_panel_frame(spec, role, ctx, physical_part_id=physical)
    require_receiving_side_panel_frame(frame, role=role, physical_part_id=physical)
    assert frame["allowed_feature_types"] == []
    lowx, lowy, highx, highy = render.material.bounds
    assert frame["finished_face_dimensions_mm"] == {
        "width": highx-lowx, "height": highy-lowy,
    }
    out = tmp_path / "real-side-panel-manufacturing"
    result = save_verified_final_scene_batch_dxf(
        [(physical, render)], out, pre_commit_guard=lambda: None,
    )
    path = out / (physical + ".dxf")
    assert result == {physical: str(path)}
    checked = verify_saved_part_render_data_dxf(render, path)
    assert checked.ok, checked.issues
    loaded = ezdxf.readfile(path)
    assert loaded.modelspace().query('*[layer=="CUTTING"]')
    assert loaded.modelspace().query('*[layer=="BEND"]')
    # Unlike a blank toy rectangle, the actual side has source-owned BLIND_HOLE
    # and right-side MARKING process layers.
    assert loaded.modelspace().query('*[layer=="BLIND_HOLE"]')
    if role == "right_side":
        assert loaded.modelspace().query('*[layer=="MARKING"]')


@pytest.mark.parametrize("fault", (
    "wrong_family", "wrong_kind", "unknown_role", "missing_role",
    "wrong_semantics", "wrong_dimensions", "missing_t", "bool_w",
    "infinite_h", "tiny_depth", "negative_fw", "missing_zl1",
    "manual_fold_profile", "assembly_state", "external_features",
    "door_frame", "inner_door_fields",
))
def test_receiving_source_side_sheet_rejects_unauthorized_manufacturing_input(fault):
    p = _part()
    if fault == "wrong_family": p["cabinet_family"] = "金庫型"
    elif fault == "wrong_kind": p["kind"] = "box_body"
    elif fault == "unknown_role": p["source_part_ref"] = "box_body:back"
    elif fault == "missing_role": del p["source_part_ref"]
    elif fault == "wrong_semantics": p["dimension_semantics"] = "part_formed_outer"
    elif fault == "wrong_dimensions": p["dimensions_mm"]["unknown"] = 3
    elif fault == "missing_t": del p["dimensions_mm"]["thickness"]
    elif fault == "bool_w": p["dimensions_mm"]["width"] = True
    elif fault == "infinite_h": p["dimensions_mm"]["height"] = float("inf")
    elif fault == "tiny_depth": p["dimensions_mm"]["depth"] = 2
    elif fault == "negative_fw": p["frame_width_mm"] = -2
    elif fault == "missing_zl1": del p["box_zl1_mm"]
    elif fault == "manual_fold_profile": p["fold_profile"] = []
    elif fault == "assembly_state": p["box_body_structure"] = {"active_type": "integral"}
    elif fault == "external_features": p["features"] = []
    elif fault == "door_frame": p["frame_edges"] = {"left": True}
    elif fault == "inner_door_fields": p["inner_door_id"] = "upper"
    with pytest.raises(PrepareEvidenceError):
        receiving_side_panel_spec_from_trusted_part(p)


def test_receiving_side_frame_forgery_rejected(tmp_path):
    root, _ = _root_with_receiving_baselines(tmp_path)
    spec, role = receiving_side_panel_spec_from_trusted_part(_part())
    physical = "whd-" + "a" * 24
    frame = receiving_side_panel_frame(
        spec, role, ManufacturingContext(resource_root=root), physical_part_id=physical,
    )
    for field, val in (
        ("allowed_feature_types", ["circle"]),
        ("origin_xyz_mm", [100.0, 0.0, 0.0]),
        ("face_role", "front"),
        ("frame_id", "side_panel:fake"),
    ):
        forged = deepcopy(frame)
        forged[field] = val
        with pytest.raises(PrepareEvidenceError):
            require_receiving_side_panel_frame(
                forged, role=role, physical_part_id=physical,
            )


def _original(tmp_path, role, *, original_circle=False):
    root, registry = _root_with_receiving_baselines(tmp_path)
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    if original_circle:
        doc.modelspace().add_circle((100, 100), 5, dxfattribs={"layer": "CUTTING"})
    source = tmp_path / "CADSplit-operator-actual-source.dxf"
    doc.saveas(source)
    request = _request()
    request["items"][0]["part"] = _part(role)
    request["items"][0]["source_document_sha256"] = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    return root, registry, source, request


@pytest.mark.parametrize("role", ("left_side", "right_side"))
def test_receiving_side_true_signed_prepare_export_and_dxf_reopen(tmp_path, role):
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
    root, _, source, request = _original(tmp_path, role)
    receipt = _prepare(request, root)
    assert receipt["status"] == "success"
    row = receipt["items"][0]
    assert row["target_frames"][0]["frame_id"].startswith(f"side_panel:{role}:")
    assert row["target_frames"][0]["allowed_feature_types"] == []
    export_request = _export_request_from_prepared(request, receipt)
    out = tmp_path / "signed-physical-receiving-side"
    result = save_trusted_door_circle_finalscene_batch(
        request, receipt, export_request,
        source_documents={request["items"][0]["item_id"]: source},
        resource_root=root, output_dir=out,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    dest = out / (row["physical_part_id"] + ".dxf")
    assert result == {row["physical_part_id"]: str(dest)}
    spec, resolved_role = receiving_side_panel_spec_from_trusted_part(_part(role))
    render = receiving_side_panel_render(
        spec, resolved_role, ManufacturingContext(resource_root=root),
    )
    verified = verify_saved_part_render_data_dxf(render, dest)
    assert verified.ok, verified.issues
    assert ezdxf.readfile(dest).modelspace().query('*[layer=="BLIND_HOLE"]')


def test_receiving_side_baseline_mutation_revokes_signed_prepare(tmp_path):
    from integration_cli.prepare_recheck import recheck_trusted_door_export
    root, _, source, request = _original(tmp_path, "left_side")
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    one = receiving_side_panel_expected_baselines(root)[1]  # right baseline also sealed
    doc = ezdxf.readfile(one)
    doc.modelspace().add_line((0, 0), (1, 1), dxfattribs={"layer": "MARKING"})
    doc.saveas(one)
    with pytest.raises(PrepareEvidenceError) as e:
        recheck_trusted_door_export(
            request, receipt, export, source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert e.value.code == "WHD_PREPARE_STALE"


def test_receiving_side_refuses_untransferred_original_circle_without_any_dxf(tmp_path):
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
    root, _, source, request = _original(tmp_path, "left_side", original_circle=True)
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    out = tmp_path / "must-not-create"
    with pytest.raises(PrepareEvidenceError) as e:
        save_trusted_door_circle_finalscene_batch(
            request, receipt, export,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=out,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert e.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not out.exists()
