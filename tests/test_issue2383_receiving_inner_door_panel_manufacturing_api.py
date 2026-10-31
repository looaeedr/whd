# -*- coding: utf-8 -*-
"""W-08: Receiving source-owned inner-door PANEL, real signed Worker DXF.

This attests one sheet and 19 mm four-fold topology; inner-door frame set,
NFB holes, source feature transfer and actual assembly remain separate gates.
"""
from copy import deepcopy
import hashlib

import ezdxf
import pytest

from ae_engine.inner_door_panels import derive_inner_door_panel
from ae_engine.manufacturing_api import (
    build_inner_door_panel_render_data,
    verify_saved_part_render_data_dxf,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
from integration_cli.worker_inner_door_panel import (
    receiving_inner_door_panel_from_trusted_part,
    resolve_receiving_inner_door_panel_frame,
    require_canonical_receiving_inner_door_panel_frame,
)
from tests.test_issue2378_prepare_batch import (
    COMMIT, ENGINE, KEY, _root, _prepare, _request,
    _export_request_from_prepared,
)


def _part():
    return {
        "kind": "inner_door", "cabinet_family": "受電箱",
        "source_part_ref": "inner_door:upper:panel",
        "dimension_semantics": "part_formed_outer",
        "inner_door_id": "upper", "inner_door_cell_key": "0:0",
        "dimensions_mm": {"width": 800.0, "height": 1100.0, "thickness": 2.0},
    }


def _source_request(tmp_path, *, source_has_hole=False):
    root, _, _ = _root(tmp_path)
    source = tmp_path / "CADSplit-confirmed-inner-panel.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    if source_has_hole:
        doc.modelspace().add_circle((60.0, 70.0), 5.0, dxfattribs={"layer": "CUTTING"})
    doc.saveas(source)
    request = _request()
    request["items"][0]["part"] = _part()
    request["items"][0]["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    return root, source, request


def test_receiving_inner_door_real_material_fold_prepare_export_and_dxf_reopen(tmp_path):
    root, source, request = _source_request(tmp_path)
    panel = receiving_inner_door_panel_from_trusted_part(request["items"][0]["part"])
    assert panel.stable_id == "inner_door:upper:panel"
    assert panel.cell_key == "0:0"
    assert panel.unfolded_width == pytest.approx(834.0)
    assert panel.unfolded_height == pytest.approx(1134.0)
    rendered = build_inner_door_panel_render_data(panel)
    assert rendered.material.is_valid and not rendered.material.is_empty
    assert rendered.fold_guides
    assert rendered.metadata["stable_id"] == "inner_door:upper:panel"
    assert rendered.metadata["inner_door_hole_feature_count"] == 0

    receipt = _prepare(request, root)
    assert receipt["status"] == "success"
    assert receipt["manufacturing_verified"] is False
    prepared_part = receipt["items"][0]
    assert prepared_part["production_scope"] == "single_part"
    frame = prepared_part["target_frames"][0]
    assert frame["frame_id"].startswith("inner_door:whd-")
    assert frame["allowed_feature_types"] == []
    require_canonical_receiving_inner_door_panel_frame(
        frame, physical_part_id=prepared_part["physical_part_id"],
    )
    x1, y1, x2, y2 = map(float, rendered.material.bounds)
    assert frame["finished_face_dimensions_mm"] == {
        "width": x2 - x1, "height": y2 - y1,
    }

    exported = _export_request_from_prepared(request, receipt)
    output = tmp_path / "true-receiving-panel-DXF"
    result = save_trusted_door_circle_finalscene_batch(
        request, receipt, exported,
        source_documents={request["items"][0]["item_id"]: source},
        resource_root=root, output_dir=output,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    physical = prepared_part["physical_part_id"]
    destination = output / (physical + ".dxf")
    assert result == {physical: str(destination)}
    assert destination.is_file() and destination.stat().st_size > 0
    reopened = ezdxf.readfile(destination).modelspace()
    assert len(reopened.query('*[layer=="CUTTING"]')) > 0
    assert len(reopened.query('*[layer=="BEND"]')) > 0
    verification = verify_saved_part_render_data_dxf(rendered, destination)
    assert verification.ok, verification.issues


@pytest.mark.parametrize("invalid", [
    "vault", "wrong_semantics", "incorrect_part_id", "missing_id",
    "unknown_cell", "missing_thickness", "extra_depth", "zero_width",
    "nan_height", "bool_thickness", "manual_fold", "fake_frame",
    "feature_holes", "fake_assembly",
])
def test_inner_panel_unverified_source_never_issues_manufacturing_token(tmp_path, invalid):
    root, _, request = _source_request(tmp_path)
    p = request["items"][0]["part"]
    if invalid == "vault":
        p["cabinet_family"] = "金庫型"
    elif invalid == "wrong_semantics":
        p["dimension_semantics"] = "cabinet_outer"
    elif invalid == "incorrect_part_id":
        p["source_part_ref"] = "inner_door:lower:panel"
    elif invalid == "missing_id":
        del p["inner_door_id"]
    elif invalid == "unknown_cell":
        p["inner_door_cell_key"] = "fake-cell"
    elif invalid == "missing_thickness":
        del p["dimensions_mm"]["thickness"]
    elif invalid == "extra_depth":
        p["dimensions_mm"]["depth"] = 350
    elif invalid == "zero_width":
        p["dimensions_mm"]["width"] = 0
    elif invalid == "nan_height":
        p["dimensions_mm"]["height"] = float("nan")
        with pytest.raises(PrepareEvidenceError):
            receiving_inner_door_panel_from_trusted_part(p)
        return
    elif invalid == "bool_thickness":
        p["dimensions_mm"]["thickness"] = True
    elif invalid == "manual_fold":
        p["fold_left_mm"] = 25.0
    elif invalid == "fake_frame":
        p["frame_edges"] = {"left": True}
    elif invalid == "feature_holes":
        p["indicator_groups"] = [2]
    elif invalid == "fake_assembly":
        p["box_z_comp_mm"] = 40.0
    request["request_digest"] = compute_wire_request_digest(request)
    with pytest.raises(Exception):
        _prepare(request, root)
    assert not (tmp_path / "cannot-write-output").exists()


def test_inner_panel_source_hole_never_silently_disappears(tmp_path):
    root, source, request = _source_request(tmp_path, source_has_hole=True)
    receipt = _prepare(request, root)
    exported = _export_request_from_prepared(request, receipt)
    target = tmp_path / "blocked-untransferred-inner-door-hole"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request, receipt, exported,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=target,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not target.exists()


def test_inner_panel_export_rejects_stale_signed_dimensions(tmp_path):
    root, source, request = _source_request(tmp_path)
    receipt = _prepare(request, root)
    exported = _export_request_from_prepared(request, receipt)
    exported["items"][0]["part"]["dimensions_mm"]["width"] += 1.0
    exported["request_digest"] = compute_wire_request_digest(exported)
    target = tmp_path / "blocked-stale-inner-door"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request, receipt, exported,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=target,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_PREPARE_STALE"
    assert not target.exists()


def test_inner_panel_size_only_frame_rejects_all_source_feature_and_origin_forgeries():
    part = _part()
    panel = receiving_inner_door_panel_from_trusted_part(part)
    physical = "whd-" + "a" * 24
    frame = resolve_receiving_inner_door_panel_frame(panel, physical_part_id=physical)
    for key, changed in (
        ("allowed_feature_types", ["circle"]),
        ("origin_xyz_mm", [100.0, 0.0, 0.0]),
        ("face_role", "front"),
    ):
        tampered = deepcopy(frame)
        tampered[key] = changed
        with pytest.raises(PrepareEvidenceError):
            require_canonical_receiving_inner_door_panel_frame(
                tampered, physical_part_id=physical,
            )
