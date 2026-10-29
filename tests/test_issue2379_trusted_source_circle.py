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


def test_verified_source_circle_becomes_whd_feature_and_real_door_dxf(tmp_path):
    """WHD owns the feature's finished-face to unfolded mapping and real DXF."""
    import math
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import generate_part
    from ae_engine.manufacturing_endcap_compat import _door_features_for_legacy_engine
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from integration_cli.source_circle_verification import verify_trusted_original_dxf_circles

    row = _source_case(tmp_path)
    original, receipt, exported, root, source = row
    assert _check(row) is None
    values = verify_trusted_original_dxf_circles(
        exported["items"][0]["features"], source_path=source,
        expected_document_sha256=original["items"][0]["source_document_sha256"],
    )
    assert len(values) == 1 and isinstance(values[0], CircleFeature)
    assert values[0].anchor is FeatureAnchor.ABSOLUTE_FINISHED_FACE
    assert values[0].offset.x == pytest.approx(20)
    assert values[0].offset.y == pytest.approx(30)
    assert values[0].diameter == pytest.approx(6)
    assert values[0].layer == "CUTTING"

    # The same WHD-owned PartSpec / AE manufacturing exporter as regular doors.
    spec = DoorPartSpec(
        width=500, height=600, thickness=2, frame_width=25,
        model_name="金庫型", features=values, feature_space="finished_face")
    context = ManufacturingContext(resource_root=root)
    mapped = _door_features_for_legacy_engine(spec, context)
    assert len(mapped) == 1
    output = tmp_path / "actual-whd-door.dxf"
    result = generate_part(spec, output, context)
    assert result.part_kind == "door" and output.is_file()
    msp = ezdxf.readfile(output).modelspace()
    matches = [
        e for e in msp.query('CIRCLE[layer=="CUTTING"]')
        if math.isclose(float(e.dxf.radius), 3.0, abs_tol=1e-6, rel_tol=0)
        and math.isclose(float(e.dxf.center.x), mapped[0].offset.x, abs_tol=1e-6, rel_tol=0)
        and math.isclose(float(e.dxf.center.y), mapped[0].offset.y, abs_tol=1e-6, rel_tol=0)
    ]
    assert len(matches) == 1, "WHD generated DXF must carry source-attested physical circle"
    assert any(e.dxf.layer == "BEND" for e in msp)


def test_verified_source_mirror_transform_mapped_once_in_whd_feature(tmp_path):
    from integration_cli.source_circle_verification import verify_trusted_original_dxf_circles
    row = _source_case(tmp_path)
    original, receipt, exported, root, source = row
    feature = exported["items"][0]["features"][0]
    feature["source_transform"]["mirror_x"] = True
    feature["source_transform"]["matrix_2x2"] = [[-1, 0], [0, 1]]
    feature["source_transform"]["translation_mm"] = [100, 0]
    feature["center_mm"] = [80, 30]
    exported["request_digest"] = compute_wire_request_digest(exported)
    assert _check(row) is None
    values = verify_trusted_original_dxf_circles(
        exported["items"][0]["features"], source_path=source,
        expected_document_sha256=original["items"][0]["source_document_sha256"],
    )
    assert len(values) == 1
    assert values[0].offset.x == pytest.approx(80)
    assert values[0].offset.y == pytest.approx(30)
    assert values[0].diameter == pytest.approx(6)


@pytest.mark.parametrize("process", ["BLIND_HOLE", "MARKING"])
def test_unapproved_source_circle_process_fails_closed_before_manufacturing(tmp_path, process):
    row = _source_case(tmp_path)
    original, receipt, exported, root, source = row
    exported["items"][0]["features"][0]["process"] = process
    exported["request_digest"] = compute_wire_request_digest(exported)
    with pytest.raises(PrepareEvidenceError) as exc:
        _check(row)
    assert exc.value.code == "WHD_SOURCE_UNVERIFIED"
    assert not (tmp_path / "worker-output-not-created").exists()
