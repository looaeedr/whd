# -*- coding: utf-8 -*-
"""W-08: actual Receiving FULL rear physical sheet, source-backed W03/W04 DXF.

The FULL panel is one independently selected physical piece from the
three-sheet Receiving factory topology. HALF and BACK_OPENING remain blocked:
their source geometry/assembly contexts require separate Gate C validation.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil

import ezdxf
import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_api import (
    save_verified_final_scene_batch_dxf,
    verify_saved_part_render_data_dxf,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
from integration_cli.worker_receiving_side_panel import (
    receiving_side_panel_spec_from_trusted_part,
    receiving_side_panel_expected_baselines,
    receiving_side_panel_render,
    receiving_side_panel_frame,
    require_receiving_side_panel_frame,
)
from tests.test_issue2378_prepare_batch import (
    HERE, COMMIT, ENGINE, KEY, _root, _prepare, _request,
    _export_request_from_prepared,
)
from tests.test_issue2383_receiving_side_panel_worker_api import _part as _side_part


def _part():
    data = _side_part("left_side")
    data["kind"] = "back_panel"
    data["source_part_ref"] = "box_body:back"
    data["back_panel_mode"] = "FULL"
    return data


def _root_with_source(tmp_path, *, original_hole=False):
    root, _, _ = _root(tmp_path)
    for baseline in receiving_side_panel_expected_baselines(root):
        baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / "基準檔" / "受電箱" / baseline.name, baseline)
    source = tmp_path / "CADSplit-verified-original-back-panel.dxf"
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = 4
    if original_hole:
        drawing.modelspace().add_circle((60, 65), 4, dxfattribs={"layer": "CUTTING"})
    drawing.saveas(source)
    request = _request()
    item = request["items"][0]
    item["part"] = _part()
    item["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    return root, source, request


def test_receiving_real_full_rear_has_four_source_slots_and_exact_dxf_reopen(tmp_path):
    root, _, _ = _root_with_source(tmp_path)
    spec, role = receiving_side_panel_spec_from_trusted_part(_part())
    assert role == "back"
    ctx = ManufacturingContext(resource_root=root)
    render = receiving_side_panel_render(spec, role, ctx)
    assert render.material.is_valid and not render.material.is_empty
    assert render.metadata["baseline_source_role"] == "back"
    assert render.metadata["baseline_source_status"] == "VERIFIED"
    assert render.metadata["baseline_feature_count"] == 4
    assert render.metadata["back_panel_mode"] == "FULL"
    assert not render.fold_guides
    assert Path(render.metadata["baseline_source_path"]).name == "後面板.dxf"
    bx0, by0, bx1, by1 = map(float, render.material.bounds)
    assert bx1 - bx0 == pytest.approx(795.0)
    assert by1 - by0 == pytest.approx(1596.0)
    physical = "whd-" + hashlib.sha256(b"rear-FULL").hexdigest()[:24]
    frame = receiving_side_panel_frame(spec, role, ctx, physical_part_id=physical)
    assert frame["frame_id"] == f"back_panel:back:{physical}:flat:size-only-v1"
    assert frame["allowed_feature_types"] == []
    require_receiving_side_panel_frame(frame, role=role, physical_part_id=physical)
    out = tmp_path / "real-back-unit-dxf"
    stored = save_verified_final_scene_batch_dxf(
        [(physical, render)], out, pre_commit_guard=lambda: None,
    )
    destination = out / (physical + ".dxf")
    assert stored == {physical: str(destination)}
    assert destination.is_file()
    check = verify_saved_part_render_data_dxf(render, destination)
    assert check.ok, check.issues
    doc = ezdxf.readfile(destination)
    cutting = [e for e in doc.modelspace()
               if e.dxftype() == "LWPOLYLINE"
               and e.dxf.layer == "CUTTING" and bool(e.closed)]
    assert len(cutting) == 5  # One actual material boundary plus four genuine slots.


def test_receiving_full_back_signed_prepare_export_and_reopen(tmp_path):
    root, source, request = _root_with_source(tmp_path)
    receipt = _prepare(request, root)
    assert receipt["status"] == "success"
    assert receipt["manufacturing_verified"] is False
    item = receipt["items"][0]
    frame = item["target_frames"][0]
    assert frame["frame_id"] == (
        f'back_panel:back:{item["physical_part_id"]}:flat:size-only-v1'
    )
    assert frame["allowed_feature_types"] == []
    assert item["production_scope"] == "single_part"
    export = _export_request_from_prepared(request, receipt)
    out = tmp_path / "receiving-real-back-signed-dxf"
    results = save_trusted_door_circle_finalscene_batch(
        request, receipt, export,
        source_documents={request["items"][0]["item_id"]: source},
        resource_root=root, output_dir=out,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    dest = out / (item["physical_part_id"] + ".dxf")
    assert results == {item["physical_part_id"]: str(dest)}
    spec, role = receiving_side_panel_spec_from_trusted_part(_part())
    expected = receiving_side_panel_render(
        spec, role, ManufacturingContext(resource_root=root),
    )
    assert verify_saved_part_render_data_dxf(expected, dest).ok
    doc = ezdxf.readfile(dest)
    assert len([e for e in doc.modelspace()
                if e.dxftype() == "LWPOLYLINE"
                and e.dxf.layer == "CUTTING" and bool(e.closed)]) == 5


@pytest.mark.parametrize("invalid", (
    "HALF", "BACK_OPENING", "lowercase", "unknown",
    "wrong_family", "wrong_role", "wrong_kind", "missing_mode",
    "extra_fold", "bool_thickness", "no_depth", "extra_dimension",
))
def test_back_panel_refuses_uncertified_original_source_or_mode(invalid):
    part = _part()
    if invalid in ("HALF", "BACK_OPENING", "unknown", "lowercase"):
        part["back_panel_mode"] = "half" if invalid == "lowercase" else invalid
    elif invalid == "wrong_family":
        part["cabinet_family"] = "金庫型"
    elif invalid == "wrong_role":
        part["source_part_ref"] = "box_body:left_side"
    elif invalid == "wrong_kind":
        part["kind"] = "side_panel"
    elif invalid == "missing_mode":
        del part["back_panel_mode"]
    elif invalid == "extra_fold":
        part["fold_profile"] = [{"length_mm": 10, "angle_deg": 90}]
    elif invalid == "bool_thickness":
        part["dimensions_mm"]["thickness"] = True
    elif invalid == "no_depth":
        del part["dimensions_mm"]["depth"]
    elif invalid == "extra_dimension":
        part["dimensions_mm"]["unverified"] = 3
    with pytest.raises(PrepareEvidenceError):
        receiving_side_panel_spec_from_trusted_part(part)


def test_back_panel_original_source_holes_cannot_be_dropped(tmp_path):
    root, source, request = _root_with_source(tmp_path, original_hole=True)
    prepared = _prepare(request, root)
    export = _export_request_from_prepared(request, prepared)
    output = tmp_path / "cannot-ignore-original-hole"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request, prepared, export,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=output,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not output.exists()


def test_back_panel_changes_to_signed_mode_or_baseline_revoke_export(tmp_path):
    from integration_cli.prepare_recheck import recheck_trusted_door_export

    root, source, request = _root_with_source(tmp_path)
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    drift = deepcopy(export)
    drift["items"][0]["part"]["back_panel_mode"] = "HALF"
    drift["request_digest"] = compute_wire_request_digest(drift)
    with pytest.raises(PrepareEvidenceError):
        recheck_trusted_door_export(
            request, receipt, drift,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    baseline = receiving_side_panel_expected_baselines(root)[2]
    doc = ezdxf.readfile(baseline)
    doc.modelspace().add_line((3, 4), (5, 6), dxfattribs={"layer": "MARKING"})
    doc.saveas(baseline)
    with pytest.raises(PrepareEvidenceError) as exc:
        recheck_trusted_door_export(
            request, receipt, export,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_PREPARE_STALE"
