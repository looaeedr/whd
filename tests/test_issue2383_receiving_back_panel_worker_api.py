# -*- coding: utf-8 -*-
"""#2383 real standalone Receiving rear-sheet W03/04 and Save→Reload DXF.

HALF source door topology, external Features and joint/assembly intentionally
remain unsupported; FULL and BACK_OPENING are separately signed and exported.
"""
from copy import deepcopy
import hashlib

import ezdxf
import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.manufacturing_api import verify_saved_part_render_data_dxf
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.worker_receiving_back_panel import (
    receiving_back_panel_spec_from_trusted_part,
    receiving_back_panel_frame,
    receiving_back_panel_render,
    require_receiving_back_panel_frame,
)
from tests.test_issue2378_prepare_batch import (
    COMMIT, ENGINE, KEY, _request, _prepare,
    _export_request_from_prepared,
)
from tests.test_issue2383_receiving_side_panel_worker_api import (
    _root_with_receiving_baselines,
)


def _part(mode="FULL"):
    return {
        "kind": "back_panel", "cabinet_family": "受電箱",
        "source_part_ref": "box_body:back", "dimension_semantics": "cabinet_outer",
        "dimensions_mm": {
            "width": 800.0, "height": 1600.0,
            "depth": 350.0, "thickness": 2.0,
        },
        "frame_width_mm": 29.0,
        "box_zl1_mm": -24.0, "box_zl2_mm": 24.0,
        "box_zr2_mm": 18.0, "back_panel_mode": mode,
    }


def _original(tmp_path, mode="FULL", *, source_hole=False):
    root, _ = _root_with_receiving_baselines(tmp_path)
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    if source_hole:
        doc.modelspace().add_circle((200.0, 200.0), 6.0, dxfattribs={"layer": "CUTTING"})
    source = tmp_path / "CADSplit-real-rear-panel-source.dxf"
    doc.saveas(source)
    request = _request()
    request["items"][0]["part"] = _part(mode)
    request["items"][0]["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    return root, source, request


@pytest.mark.parametrize("mode,expected_contours", [
    ("FULL", 5), ("BACK_OPENING", 6),
])
def test_receiving_back_panel_real_source_four_slots_optional_opening_to_dxf(
    tmp_path, mode, expected_contours,
):
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
    root, source, request = _original(tmp_path, mode)
    spec = receiving_back_panel_spec_from_trusted_part(request["items"][0]["part"])
    ctx = ManufacturingContext(resource_root=root)
    render = receiving_back_panel_render(spec, ctx)
    assert render.material.is_valid and render.material.area > 0
    assert render.metadata["baseline_source_status"] == "VERIFIED"
    assert render.metadata["baseline_source_role"] == "back"
    assert render.metadata["baseline_feature_count"] == expected_contours - 1
    assert render.metadata["back_panel_mode"] == mode
    assert not render.fold_guides  # flat physical sheet; no synthetic BEND
    msp_closed = tuple(p for p in render.scene.primitives
                       if p.layer == "CUTTING" and getattr(p, "closed", False))
    assert len(msp_closed) == expected_contours

    prepared = _prepare(request, root)
    assert prepared["status"] == "success"
    identity = prepared["items"][0]["physical_part_id"]
    frame = prepared["items"][0]["target_frames"][0]
    assert frame["frame_id"] == f"back_panel:{mode}:{identity}:flat:size-only-v1"
    require_receiving_back_panel_frame(frame, mode=mode, physical_part_id=identity)
    assert frame["allowed_feature_types"] == []
    assert receiving_back_panel_frame(spec, ctx, physical_part_id=identity) == frame
    x0, y0, x1, y1 = render.material.bounds
    assert frame["finished_face_dimensions_mm"] == {
        "width": x1-x0, "height": y1-y0,
    }

    out = tmp_path / f"receiving-real-back-{mode}"
    exported = save_trusted_door_circle_finalscene_batch(
        request, prepared, _export_request_from_prepared(request, prepared),
        source_documents={request["items"][0]["item_id"]: source},
        resource_root=root, output_dir=out,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    final = out / (identity + ".dxf")
    assert exported == {identity: str(final)} and final.is_file()
    reopened = ezdxf.readfile(final)
    closed = tuple(row for row in reopened.modelspace().query('LWPOLYLINE[layer=="CUTTING"]')
                   if row.closed)
    assert len(closed) == expected_contours
    assert not reopened.modelspace().query('*[layer=="BEND"]')
    assert verify_saved_part_render_data_dxf(render, final).ok


@pytest.mark.parametrize("field", [
    "wrong_family", "wrong_identity", "bad_semantics", "half",
    "absent_mode", "missing_depth", "extra_dimension", "zero_w",
    "extra_factory", "manual_fold", "nonfinite", "wrong_type",
])
def test_receiving_back_panel_refuses_unsupported_or_forged_source(field):
    part = _part()
    if field == "wrong_family":
        part["cabinet_family"] = "金庫型"
    elif field == "wrong_identity":
        part["source_part_ref"] = "box_body:right_side"
    elif field == "bad_semantics":
        part["dimension_semantics"] = "part_formed_outer"
    elif field == "half":
        part["back_panel_mode"] = "HALF"
    elif field == "absent_mode":
        del part["back_panel_mode"]
    elif field == "missing_depth":
        del part["dimensions_mm"]["depth"]
    elif field == "extra_dimension":
        part["dimensions_mm"]["rear_fold"] = 12
    elif field == "zero_w":
        part["dimensions_mm"]["width"] = 0
    elif field == "extra_factory":
        part["back_panel_upper_section_mm"] = 1100
    elif field == "manual_fold":
        part["fold_profile"] = []
    elif field == "nonfinite":
        part["box_zl2_mm"] = float("nan")
    elif field == "wrong_type":
        part["frame_width_mm"] = True
    with pytest.raises(PrepareEvidenceError):
        receiving_back_panel_spec_from_trusted_part(part)


def test_receiving_back_frame_denies_external_source_mappings(tmp_path):
    root, _, _ = _original(tmp_path)
    spec = receiving_back_panel_spec_from_trusted_part(_part())
    frame = receiving_back_panel_frame(
        spec, ManufacturingContext(resource_root=root),
        physical_part_id="whd-" + "a"*24,
    )
    for field, val in (
        ("face_role", "front"),
        ("allowed_feature_types", ["circle"]),
        ("origin_xyz_mm", [15, 0, 0]),
        ("frame_id", "back_panel:fake"),
    ):
        changed = deepcopy(frame)
        changed[field] = val
        with pytest.raises(PrepareEvidenceError):
            require_receiving_back_panel_frame(
                changed, mode="FULL", physical_part_id="whd-" + "a"*24,
            )


def test_receiving_back_panel_source_circle_fails_before_export(tmp_path):
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
    root, source, request = _original(tmp_path, source_hole=True)
    receipt = _prepare(request, root)
    output = tmp_path / "no-untransferred-cutting"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request, receipt, _export_request_from_prepared(request, receipt),
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=output,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not output.exists()


def test_receiving_back_panel_attested_coupled_baseline_change_revokes_prepare(tmp_path):
    from integration_cli.prepare_recheck import recheck_trusted_door_export
    from integration_cli.worker_receiving_side_panel import receiving_side_panel_expected_baselines
    root, source, request = _original(tmp_path)
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    # Even the opposite side's source was included in this signed batch.
    path = receiving_side_panel_expected_baselines(root)[0]
    doc = ezdxf.readfile(path)
    doc.modelspace().add_line((0, 0), (1, 1), dxfattribs={"layer": "MARKING"})
    doc.saveas(path)
    with pytest.raises(PrepareEvidenceError) as exc:
        recheck_trusted_door_export(
            request, receipt, export,
            resource_root=root, engine_commit=COMMIT,
            engine_sha256=ENGINE, build_id="test-only-source",
            worker_key=KEY,
        )
    assert exc.value.code == "WHD_PREPARE_STALE"


def test_receiving_back_panel_signed_mode_change_prevents_dxfs(tmp_path):
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
    root, source, request = _original(tmp_path)
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    export["items"][0]["part"]["back_panel_mode"] = "BACK_OPENING"
    export["request_digest"] = compute_wire_request_digest(export)
    out = tmp_path / "no-stale-mode-export"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request, receipt, export,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=out,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_PREPARE_STALE"
    assert not out.exists()
