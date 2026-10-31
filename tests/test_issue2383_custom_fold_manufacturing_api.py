# -*- coding: utf-8 -*-
"""#2383 Custom Fold real canonical geometry/Save→Reload, not capability-only."""
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
from integration_cli.worker_custom_fold import (
    custom_fold_spec_from_trusted_prepared_part,
    resolve_custom_fold_size_only_frame,
    require_canonical_custom_fold_size_only_frame,
)


def _part(family="金庫型", axis="X"):
    return {
        "kind": "custom_fold", "cabinet_family": family,
        "source_part_ref": "custom:17", "dimension_semantics": "part_formed_outer",
        "dimensions_mm": {"thickness": 2.0},
        "fold_axis": axis,
        "transverse_length_mm": 300.0,
        "fold_profile": [
            {"length_mm": 15.0, "angle_deg": -90, "phase6_key": "custom_flange",
             "formed_length_mm": 17.0},
            {"length_mm": 98.0, "angle_deg": None, "phase6_key": "custom_face",
             "formed_length_mm": 100.0, "core": "CUSTOM_FACE"},
        ],
    }


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
@pytest.mark.parametrize("axis", ["X", "Y"])
def test_both_family_custom_fold_actual_flat_bend_and_reopen(tmp_path, family, axis):
    part = _part(family, axis)
    spec = custom_fold_spec_from_trusted_prepared_part(part)
    assert spec.physical_id == "custom:17"
    assert spec.fold_axis == axis
    render = build_part_render_data(spec)
    assert render.material.is_valid and render.material.area > 0
    assert render.fold_guides
    assert render.metadata["assembly_placement"] == "unassigned"

    identity = "whd-" + hashlib.sha256(f"{family}-{axis}".encode()).hexdigest()[:24]
    frame = resolve_custom_fold_size_only_frame(
        spec, ManufacturingContext(), physical_part_id=identity,
    )
    require_canonical_custom_fold_size_only_frame(frame, physical_part_id=identity)
    assert frame["allowed_feature_types"] == []
    assert "no certified CADSplit source Feature" in frame["origin_definition"]
    bounds = render.material.bounds
    assert frame["finished_face_dimensions_mm"] == {
        "width": bounds[2] - bounds[0],
        "height": bounds[3] - bounds[1],
    }
    out = tmp_path / "custom-fold-physical-DXF"
    # Engine-unit stage only; installed Worker supplies the authenticated
    # pre-commit guard in the end-to-end test below.
    result = save_verified_final_scene_batch_dxf(
        [(identity, render)], out, pre_commit_guard=lambda: None,
    )
    path = out / (identity + ".dxf")
    assert path.is_file()
    assert result == {identity: str(path)}
    verify = verify_saved_part_render_data_dxf(render, path)
    assert verify.ok, verify.issues
    read = ezdxf.readfile(path)
    assert len(read.modelspace().query('*[layer=="BEND"]')) >= 1
    assert len(read.modelspace().query('*[layer=="CUTTING"]')) >= 1


@pytest.mark.parametrize("change", [
    "missing_profile", "missing_axis", "bad_axis", "fake_identity",
    "nonpositive_span", "wrong_family", "wrong_semantics", "door_override",
    "nonpositive_length", "invalid_angle", "terminal_bend", "no_bend",
    "additional_dimension", "overlong_rows", "unknown_row_field",
])
def test_custom_fold_rejects_unverified_physical_semantics(change):
    p = _part()
    if change == "missing_profile":
        del p["fold_profile"]
    elif change == "missing_axis":
        del p["fold_axis"]
    elif change == "bad_axis":
        p["fold_axis"] = "Z"
    elif change == "fake_identity":
        p["source_part_ref"] = "custom:undefined"
    elif change == "nonpositive_span":
        p["transverse_length_mm"] = 0
    elif change == "wrong_family":
        p["cabinet_family"] = "UNKNOWN"
    elif change == "wrong_semantics":
        p["dimension_semantics"] = "cabinet_outer"
    elif change == "door_override":
        p["frame_width_mm"] = 25
    elif change == "nonpositive_length":
        p["fold_profile"][0]["length_mm"] = -5
    elif change == "invalid_angle":
        p["fold_profile"][0]["angle_deg"] = 45
    elif change == "terminal_bend":
        p["fold_profile"][-1]["angle_deg"] = 90
    elif change == "no_bend":
        p["fold_profile"][0]["angle_deg"] = None
    elif change == "additional_dimension":
        p["dimensions_mm"]["width"] = 500
    elif change == "overlong_rows":
        p["fold_profile"] = p["fold_profile"] * 40
    elif change == "unknown_row_field":
        p["fold_profile"][0]["mystery"] = "X"
    with pytest.raises(PrepareEvidenceError):
        custom_fold_spec_from_trusted_prepared_part(p)


def test_custom_fold_size_only_frame_rejects_tamper():
    spec = custom_fold_spec_from_trusted_prepared_part(_part())
    identity = "whd-" + "c" * 24
    frame = resolve_custom_fold_size_only_frame(
        spec, ManufacturingContext(), physical_part_id=identity,
    )
    for field, value in (
        ("face_role", "front"),
        ("allowed_feature_types", ["circle"]),
        ("origin_xyz_mm", [100.0, 0.0, 0.0]),
    ):
        bad = deepcopy(frame)
        bad[field] = value
        with pytest.raises(PrepareEvidenceError):
            require_canonical_custom_fold_size_only_frame(bad, physical_part_id=identity)


@pytest.mark.parametrize("family,axis", [
    ("金庫型", "X"), ("金庫型", "Y"), ("受電箱", "X"), ("受電箱", "Y"),
])
def test_signed_both_family_custom_fold_prepare_export_and_dxf_reopen(tmp_path, family, axis):
    from tests.test_issue2378_prepare_batch import (
        COMMIT, ENGINE, KEY, _root, _prepare, _request,
        _export_request_from_prepared,
    )
    from integration_cli.request_canonical import compute_wire_request_digest
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch

    root, _, _ = _root(tmp_path)
    source = tmp_path / "CADSplit-authenticated-empty-original.dxf"
    dxf = ezdxf.new("R2010")
    dxf.header["$INSUNITS"] = 4
    dxf.saveas(source)
    original = _request()
    item = original["items"][0]
    item["part"] = _part(family, axis)
    item["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    original["request_digest"] = compute_wire_request_digest(original)
    prepared = _prepare(original, root)
    assert prepared["status"] == "success"
    frame = prepared["items"][0]["target_frames"][0]
    assert frame["frame_id"].startswith("custom_fold:")
    assert frame["allowed_feature_types"] == []
    export = _export_request_from_prepared(original, prepared)
    path = tmp_path / "real-custom-fold"
    actual = save_trusted_door_circle_finalscene_batch(
        original, prepared, export,
        source_documents={item["item_id"]: source}, resource_root=root,
        output_dir=path, engine_commit=COMMIT, engine_sha256=ENGINE,
        build_id="test-only-source", worker_key=KEY,
    )
    identity = prepared["items"][0]["physical_part_id"]
    dxf_path = path / (identity + ".dxf")
    assert actual == {identity: str(dxf_path)}
    assert dxf_path.is_file()
    scene = build_part_render_data(custom_fold_spec_from_trusted_prepared_part(item["part"]))
    assert verify_saved_part_render_data_dxf(scene, dxf_path).ok
    reopened = ezdxf.readfile(dxf_path)
    assert len(reopened.modelspace().query('*[layer=="BEND"]')) > 0


def test_custom_fold_external_source_hole_is_not_silently_dropped(tmp_path):
    from tests.test_issue2378_prepare_batch import (
        COMMIT, ENGINE, KEY, _root, _prepare, _request,
        _export_request_from_prepared,
    )
    from integration_cli.request_canonical import compute_wire_request_digest
    from integration_cli.verified_door_finalscene import save_trusted_door_circle_finalscene_batch

    root, _, _ = _root(tmp_path)
    source = tmp_path / "custom-source-with-circle.dxf"
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = 4
    drawing.modelspace().add_circle((30, 30), 5, dxfattribs={"layer": "CUTTING"})
    drawing.saveas(source)
    request = _request()
    request["items"][0]["part"] = _part()
    request["items"][0]["source_document_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    request["request_digest"] = compute_wire_request_digest(request)
    receipt = _prepare(request, root)
    export = _export_request_from_prepared(request, receipt)
    path = tmp_path / "must-not-write"
    with pytest.raises(PrepareEvidenceError) as exc:
        save_trusted_door_circle_finalscene_batch(
            request, receipt, export,
            source_documents={request["items"][0]["item_id"]: source},
            resource_root=root, output_dir=path,
            engine_commit=COMMIT, engine_sha256=ENGINE,
            build_id="test-only-source", worker_key=KEY,
        )
    assert exc.value.code == "WHD_FINALSCENE_UNVERIFIED"
    assert not path.exists()
