# -*- coding: utf-8 -*-
"""#2379 wire Feature claims: reject bad shapes/transforms before any DXF stage.

These tests do not certify CADSplit's original entities or enable public export.
"""
from copy import deepcopy

import pytest

from integration_cli.feature_preflight import validate_wire_features_against_prepared_frame
from integration_cli.prepare_evidence import PrepareEvidenceError
from integration_cli.request_canonical import compute_wire_request_digest
from tests.test_issue2378_prepare_batch import (
    _export_request_from_prepared, _prepare, _recheck, _request, _root,
)


def _frame():
    return {
        "frame_id": "door:witness:front", "face_role": "front",
        "viewed_from": "along_normal", "units": "mm",
        "allowed_feature_types": ["circle", "rect", "profile"],
        "finished_face_dimensions_mm": {"width": 100.0, "height": 80.0},
    }


def _circle(frame):
    return {
        "feature_id": "hole-1", "source_ref": "source-circle-1",
        "type": "circle", "coordinate_space": "finished_face",
        "target_frame_id": frame["frame_id"], "units": "mm",
        "face_role": frame["face_role"],
        "viewed_from": frame["viewed_from"], "process": "THROUGH_CUT",
        "center_mm": [40.0, 40.0], "radius_mm": 5.0,
        "source_transform": {
            "source_frame_id": "CAD-SOURCE-1", "source_units": "mm",
            "source_to_mm_scale": 1.0, "unit_authority": "DXF-HEADER",
            "matrix_2x2": [[1, 0], [0, 1]], "translation_mm": [0, 0],
            "rotation_deg": 0, "mirror_x": False, "mirror_y": False,
            "source_geometry_sha256": "f" * 64,
            "source_entity_refs": ["handle-01"],
            "source_dimensions_mm": {"width": 100.0, "height": 80.0},
            "target_dimensions_mm": deepcopy(frame["finished_face_dimensions_mm"]),
        },
    }


@pytest.mark.parametrize("variation", [
    "circle", "rect90", "closed_profile", "mirror_x", "quarter_turn",
    "inch_scale",
])
def test_valid_wire_envelope_does_not_claim_original_source_certification(variation):
    frame = _frame()
    f = _circle(frame)
    t = f["source_transform"]
    if variation == "rect90":
        f.update(type="rect", width_mm=10, height_mm=20, rotation_deg=90)
        del f["radius_mm"]
    elif variation == "closed_profile":
        f.update(type="profile", points_mm=[[10,10],[50,10],[50,60],[10,60]],closed=True)
        del f["center_mm"]
        del f["radius_mm"]
    elif variation == "mirror_x":
        t["mirror_x"] = True
        t["matrix_2x2"] = [[-1,0],[0,1]]
    elif variation == "quarter_turn":
        t["rotation_deg"] = 90
        t["matrix_2x2"] = [[0,-1],[1,0]]
    elif variation == "inch_scale":
        t["source_units"] = "inch"
        t["source_to_mm_scale"] = 25.4
    assert validate_wire_features_against_prepared_frame([f], frame) is None


@pytest.mark.parametrize("mutation", [
    "duplicate_id", "outside_circle", "outside_rect", "crossed_profile",
    "collapsed_profile", "target_dimensions", "matrix_singular",
    "matrix_shear", "rotation_inconsistent", "mirror_inconsistent",
    "unit_scale", "nan_translation", "bool_radius", "wrong_face",
    "wrong_target_frame", "unsupported_kind", "missing_source_scale",
])
def test_bad_wire_feature_rejected_before_manufacturing(mutation):
    frame = _frame()
    f = _circle(frame)
    values = [f]
    t = f["source_transform"]
    if mutation == "duplicate_id":
        values.append(deepcopy(f))
    elif mutation == "outside_circle":
        f["center_mm"] = [2, 2]
    elif mutation == "outside_rect":
        f.update(type="rect", width_mm=40, height_mm=30, rotation_deg=0)
        del f["radius_mm"]
        f["center_mm"] = [95, 70]
    elif mutation == "crossed_profile":
        f.update(type="profile", points_mm=[[10,10],[65,65],[10,65],[65,10]],closed=True)
        del f["center_mm"]
        del f["radius_mm"]
    elif mutation == "collapsed_profile":
        f.update(type="profile", points_mm=[[10,10],[10,10],[10,10]],closed=True)
        del f["center_mm"]
        del f["radius_mm"]
    elif mutation == "target_dimensions":
        t["target_dimensions_mm"]["width"] = 101
    elif mutation == "matrix_singular":
        t["matrix_2x2"] = [[0,0],[0,0]]
    elif mutation == "matrix_shear":
        t["matrix_2x2"] = [[1,0.2],[0,1]]
    elif mutation == "rotation_inconsistent":
        t["rotation_deg"] = 90
    elif mutation == "mirror_inconsistent":
        t["mirror_x"] = True
    elif mutation == "unit_scale":
        t["source_units"] = "inch"
    elif mutation == "nan_translation":
        t["translation_mm"][0] = float("nan")
    elif mutation == "bool_radius":
        f["radius_mm"] = True
    elif mutation == "wrong_face":
        f["face_role"] = "back"
    elif mutation == "wrong_target_frame":
        f["target_frame_id"] = "untrusted-frame"
    elif mutation == "unsupported_kind":
        frame["allowed_feature_types"] = ["rect"]
    elif mutation == "missing_source_scale":
        del t["source_to_mm_scale"]
    with pytest.raises(PrepareEvidenceError) as exc:
        validate_wire_features_against_prepared_frame(values, frame)
    assert exc.value.code == "WHD_FEATURE_UNVERIFIED"


def test_valid_feature_wire_envelope_rechecks_before_export_but_writes_nothing(tmp_path):
    root, _, _ = _root(tmp_path)
    original = _request()
    receipt = _prepare(original, root)
    request = _export_request_from_prepared(original, receipt)
    frame = receipt["items"][0]["target_frames"][0]
    f = _circle(frame)
    face = frame["finished_face_dimensions_mm"]
    f["center_mm"] = [face["width"] / 2, face["height"] / 2]
    f["source_transform"]["target_dimensions_mm"] = deepcopy(face)
    request["items"][0]["features"] = [f]
    request["request_digest"] = compute_wire_request_digest(request)
    assert _recheck(original, receipt, request, root) is None
    assert receipt["manufacturing_verified"] is False
    assert not (tmp_path / "worker-output-not-created").exists()


def test_recheck_rejects_bad_feature_even_with_recomputed_canonical_digest(tmp_path):
    root, _, _ = _root(tmp_path)
    original = _request()
    receipt = _prepare(original, root)
    request = _export_request_from_prepared(original, receipt)
    frame = receipt["items"][0]["target_frames"][0]
    f = _circle(frame)
    face = frame["finished_face_dimensions_mm"]
    f["center_mm"] = [face["width"] / 2, face["height"] / 2]
    f["source_transform"]["target_dimensions_mm"] = deepcopy(face)
    f["source_transform"]["matrix_2x2"] = [[1, 0.5], [0, 1]]
    request["items"][0]["features"] = [f]
    request["request_digest"] = compute_wire_request_digest(request)
    with pytest.raises(PrepareEvidenceError) as exc:
        _recheck(original, receipt, request, root)
    assert exc.value.code == "WHD_FEATURE_UNVERIFIED"
    assert not (tmp_path / "worker-output-not-created").exists()
