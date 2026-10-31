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
