# -*- coding: utf-8 -*-
"""#2383: three real Receiving A/B/D sourced inner-door frame physical DXFs.

One signed Worker W03→W04 batch uses the installed resource-root 框.dxf,
not the GUI preview, C divider, default repo copy or fabricated Fold.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil

import ezdxf
import pytest

from ae_engine.manufacturing_api import (
    build_inner_door_frame_render_data,
    verify_saved_part_render_data_dxf,
)
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch
from integration_cli.worker_inner_door_frame import (
    receiving_inner_door_frame_from_trusted_part,
    receiving_inner_door_frame_size_only_frame,
    require_receiving_inner_door_frame_size_only_frame,
    source_frame_baseline,
)
from tests.test_issue2378_prepare_batch import (
    COMMIT, ENGINE, KEY, HERE, _root, _request, _prepare,
    _export_request_from_prepared,
)


def _part(side, span):
    return {
        "kind": "inner_door", "cabinet_family": "受電箱",
        "source_part_ref": f"inner_door:upper:{side}_frame",
        "dimension_semantics": "part_formed_outer",
        "dimensions_mm": {"thickness": 2.0},
        "inner_door_id": "upper", "inner_door_frame_side": side,
        "inner_door_frame_span_mm": span,
    }


def _source_and_request(tmp_path, *, with_hole=False, count=3):
    root, _, _ = _root(tmp_path)
    baseline = source_frame_baseline(root)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "基準檔" / "受電箱" / "框.dxf", baseline)
    original = tmp_path / "CADSplit-confirmed-empty-original.dxf"
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = 4
    if with_hole:
        drawing.modelspace().add_circle((40, 50), 4, dxfattribs={"layer": "CUTTING"})
    drawing.saveas(original)
    request = _request(count=count)
    for row, (side, span) in zip(request["items"], [
        ("left", 1098.0), ("right", 1098.0), ("top", 696.0),
    ]):
        row["part"] = _part(side, span)
        row["source_document_sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    return root, baseline, original, request


def _export(root, original, request, receipt, out):
    return save_trusted_door_circle_finalscene_batch(
        request, receipt, _export_request_from_prepared(request, receipt),
        source_documents={x["item_id"]: original for x in request["items"]},
        resource_root=root, output_dir=out,
        engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )


def test_receiving_three_source_A_B_D_real_Fold_authenticated_dxf_batch(tmp_path):
    root, baseline, original, request = _source_and_request(tmp_path)
    receipt = _prepare(request, root)
    assert receipt["status"] == "success" and not receipt["manufacturing_verified"]
    out = tmp_path / "three-real-DXF"
    exported = _export(root, original, request, receipt, out)
    assert len(exported) == 3
    for row, prepared, expected_tag in zip(
        request["items"], receipt["items"], ("A", "B", "D"),
    ):
        physical = prepared["physical_part_id"]
        assert prepared["target_frames"][0]["allowed_feature_types"] == []
        frame = receiving_inner_door_frame_from_trusted_part(row["part"])
        assert frame.stable_id == row["part"]["source_part_ref"]
        assert len(frame.fold_profile) == (4 if frame.side == "right" else 3)
        target = receiving_inner_door_frame_size_only_frame(
            frame, root, physical_part_id=physical,
        )
        assert target == prepared["target_frames"][0]
        require_receiving_inner_door_frame_size_only_frame(
            target, frame_side=frame.side, physical_part_id=physical,
        )
        scene = build_inner_door_frame_render_data(frame, resource_root=root)
        assert scene.metadata["receiving_frame_source_tag"] == expected_tag
        assert scene.metadata["receiving_frame_source_sha256"] == hashlib.sha256(baseline.read_bytes()).hexdigest()
        assert scene.fold_guides and scene.material.is_valid
        dest = out / f"{physical}.dxf"
        assert exported[physical] == str(dest) and dest.is_file()
        actual = ezdxf.readfile(dest)
        assert actual.modelspace().query('*[layer=="CUTTING"]')
        assert actual.modelspace().query('*[layer=="BEND"]')
        assert verify_saved_part_render_data_dxf(scene, dest).ok


@pytest.mark.parametrize("change", [
    "missing_side", "wrong_family", "bottom", "invalid_role", "wrong_ref",
    "bad_id", "negative_span", "too_short", "nan_span", "bool_t",
    "extra_width", "manual_fold", "cell_key", "source_hole",
])
def test_receiving_A_B_D_frame_rejects_unconfirmed_part_semantics(change):
    part = _part("left", 1098.0)
    if change == "missing_side":
        del part["inner_door_frame_side"]
    elif change == "wrong_family":
        part["cabinet_family"] = "金庫型"
    elif change == "bottom":
        part["inner_door_frame_side"] = "bottom"
        part["source_part_ref"] = "inner_door:upper:bottom_frame"
    elif change == "invalid_role":
        part["inner_door_frame_side"] = "divider"
        part["source_part_ref"] = "inner_door:upper:divider_frame"
    elif change == "wrong_ref":
        part["source_part_ref"] = "inner_door:other:left_frame"
    elif change == "bad_id":
        part["inner_door_id"] = "../upper"
    elif change == "negative_span":
        part["inner_door_frame_span_mm"] = -200
    elif change == "too_short":
        part["inner_door_frame_span_mm"] = 110
    elif change == "nan_span":
        part["inner_door_frame_span_mm"] = float("nan")
    elif change == "bool_t":
        part["dimensions_mm"]["thickness"] = True
    elif change == "extra_width":
        part["dimensions_mm"]["width"] = 500
    elif change == "manual_fold":
        part["fold_profile"] = []
    elif change == "cell_key":
        part["inner_door_cell_key"] = "0:0"
    elif change == "source_hole":
        part["features"] = []
    with pytest.raises(PrepareEvidenceError):
        receiving_inner_door_frame_from_trusted_part(part)


def test_receiving_frames_original_source_unmapped_hole_blocks_entire_atomic_batch(tmp_path):
    root, _, original, request = _source_and_request(tmp_path, with_hole=True)
    receipt = _prepare(request, root)
    out = tmp_path / "must-never-export"
    with pytest.raises(PrepareEvidenceError) as exc:
        _export(root, original, request, receipt, out)
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not out.exists()


def test_receiving_frame_baseline_changed_after_W03_prevents_export(tmp_path):
    root, baseline, original, request = _source_and_request(tmp_path)
    receipt = _prepare(request, root)
    # A legitimate resource is replaced with different bytes after sealing.
    baseline.write_bytes(b"tampered non-DXF baseline")
    with pytest.raises(PrepareEvidenceError):
        _export(root, original, request, receipt, tmp_path / "blocked-stale")
    assert not (tmp_path / "blocked-stale").exists()


def test_receiving_frame_size_only_cannot_authorize_source_features(tmp_path):
    root, _, _, _ = _source_and_request(tmp_path)
    physical = "whd-" + "a" * 24
    frame = receiving_inner_door_frame_from_trusted_part(_part("top", 696.0))
    target = receiving_inner_door_frame_size_only_frame(frame, root, physical_part_id=physical)
    for key, value in (
        ("allowed_feature_types", ["circle"]),
        ("origin_xyz_mm", [2, 0, 0]),
        ("face_role", "front"),
    ):
        changed = deepcopy(target)
        changed[key] = value
        with pytest.raises(PrepareEvidenceError):
            require_receiving_inner_door_frame_size_only_frame(
                changed, frame_side="top", physical_part_id=physical,
            )
