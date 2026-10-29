# -*- coding: utf-8 -*-
"""#2379 RED/GREEN: WHD must reopen trusted original DXF circles, not trust wire claims."""
from copy import deepcopy
import hashlib

import ezdxf
import pytest

from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from tests.test_issue2378_prepare_batch import _export_request_from_prepared, _prepare, _recheck, _request, _root
from tests.test_issue2379_wire_feature_preflight import _circle


def _source_case(tmp_path, *, inch=False):
    source = tmp_path / "CAD-original.dxf"
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 1 if inch else 4
    x, y, radius = (1.0, 2.0, 0.25) if inch else (20.0, 30.0, 3.0)
    circle = doc.modelspace().add_circle((x, y), radius, dxfattribs={"layer": "CUTTING"})
    handle = circle.dxf.handle
    doc.saveas(source)
    original = _request()
    original["items"][0]["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    original["request_digest"] = compute_wire_request_digest(original)
    root, _, _ = _root(tmp_path)
    receipt = _prepare(original, root)
    exported = _export_request_from_prepared(original, receipt)
    face = receipt["items"][0]["target_frames"][0]
    wire = _circle(face)
    wire["source_transform"]["target_dimensions_mm"] = deepcopy(face["finished_face_dimensions_mm"])
    wire["source_transform"]["source_entity_refs"] = [handle]
    if inch:
        wire["center_mm"] = [25.4, 50.8]
        wire["radius_mm"] = 6.35
        wire["source_transform"]["source_units"] = "inch"
        wire["source_transform"]["source_to_mm_scale"] = 25.4
    else:
        wire["center_mm"] = [20, 30]
        wire["radius_mm"] = 3
    exported["items"][0]["features"] = [wire]
    exported["request_digest"] = compute_wire_request_digest(exported)
    return original, receipt, exported, root, source


def _check(row, *, trusted=True):
    original, receipt, exported, root, source = row
    args = {"source_documents": {original["items"][0]["item_id"]: source}} if trusted else {}
    return _recheck(original, receipt, exported, root, **args)


@pytest.mark.parametrize("inch", [False, True])
def test_trusted_source_circle_reopened_and_transformed_once(tmp_path, inch):
    row = _source_case(tmp_path, inch=inch)
    assert _check(row) is None
    assert row[1]["manufacturing_verified"] is False
    assert not (tmp_path / "worker-output-not-created").exists()


@pytest.mark.parametrize("fault", [
    "missing_trusted_source", "false_target_center", "false_radius",
    "unknown_source_handle", "changed_document_bytes", "wrong_source_units",
    "claimed_rect_not_supported", "duplicate_source_handle",
])
def test_recheck_rejects_unproven_source_geometry_before_staging(tmp_path, fault):
    row = _source_case(tmp_path)
    original, receipt, exported, root, source = row
    feat = exported["items"][0]["features"][0]
    if fault == "false_target_center":
        feat["center_mm"][0] += 5
    elif fault == "false_radius":
        feat["radius_mm"] += 1
    elif fault == "unknown_source_handle":
        feat["source_transform"]["source_entity_refs"] = ["FFFABC"]
    elif fault == "changed_document_bytes":
        source.write_bytes(source.read_bytes() + b"\n")
    elif fault == "wrong_source_units":
        feat["source_transform"]["source_units"] = "inch"
        feat["source_transform"]["source_to_mm_scale"] = 25.4
    elif fault == "claimed_rect_not_supported":
        feat["type"] = "rect"
        feat["width_mm"] = 6
        feat["height_mm"] = 6
        feat["rotation_deg"] = 0
        del feat["radius_mm"]
    elif fault == "duplicate_source_handle":
        another = deepcopy(feat)
        another["feature_id"] = "hole-2"
        another["source_ref"] = "claimed-2"
        exported["items"][0]["features"].append(another)
    exported["request_digest"] = compute_wire_request_digest(exported)
    with pytest.raises(PrepareEvidenceError) as exc:
        _check(row, trusted=(fault != "missing_trusted_source"))
    assert exc.value.code == "WHD_SOURCE_UNVERIFIED"
    assert not (tmp_path / "worker-output-not-created").exists()


def test_symlinked_source_rejected_before_render(tmp_path):
    row = _source_case(tmp_path)
    source = row[4]
    link = tmp_path / "aliased-source.dxf"
    try:
        link.symlink_to(source)
    except (NotImplementedError, OSError):
        pytest.skip("filesystem has no symlinks")
    with pytest.raises(PrepareEvidenceError) as exc:
        _recheck(row[0], row[1], row[2], row[3],
                 source_documents={row[0]["items"][0]["item_id"]: link})
    assert exc.value.code == "WHD_SOURCE_UNVERIFIED"
