# -*- coding: utf-8 -*-
"""#2378 W-03 resource/Policy fingerprint preflight, no manufactured Frames."""
from dataclasses import replace
from pathlib import Path

import pytest

from integration_cli.prepare_evidence import (
    PrepareEvidenceError, assert_snapshot_current, build_resource_evidence,
    resolve_authoritative_door_inputs,
)

ENGINE_HASH = "a" * 64
COMMIT = "b" * 40


def _source(tmp_path):
    root = tmp_path / "中文 資源根"
    registry = root / "基準檔/截角資料庫/certified_relief_rules.json"
    baseline = root / "基準檔/金庫型/門.dxf"
    registry.parent.mkdir(parents=True)
    baseline.parent.mkdir(parents=True)
    registry.write_text('{"rule":"source-A"}', encoding="utf-8")
    baseline.write_bytes(b"real-source-bytes-for-test-only")
    return root, registry, baseline


def _arguments(root):
    return dict(
        resource_root=root,
        registry_path="基準檔/截角資料庫/certified_relief_rules.json",
        baseline_paths=["基準檔/金庫型/門.dxf"],
        resolved_policy={"frame_width": 25.0, "door_gap_w": 0.0},
        locked_inputs={"job_id": "job001", "items": [
            {"physical_part_id": "door-1", "cabinet_outer_width_mm": 500.0}
        ]},
        engine_commit=COMMIT,
        engine_sha256=ENGINE_HASH,
        build_id="source-only-test",
    )


def test_same_bytes_same_environment_digest_even_with_chinese_paths(tmp_path):
    root, _, _ = _source(tmp_path)
    args = _arguments(root)
    first = build_resource_evidence(**args)
    second = build_resource_evidence(**args)
    assert first == second
    assert first["snapshot"]["registry"]["sha256"] != "0" * 64
    assert first["snapshot"]["baselines"][0]["path"] == "基準檔/金庫型/門.dxf"
    assert_snapshot_current(first, second)
    assert "prepare_token" not in first
    assert "target_frames" not in first


@pytest.mark.parametrize("changed", [
    "registry", "baseline", "policy", "locked_width", "engine", "commit",
    "build", "frame_revision",
])
def test_stale_on_any_frozen_input_change(tmp_path, changed):
    root, registry, baseline = _source(tmp_path)
    args = _arguments(root)
    first = build_resource_evidence(**args)
    if changed == "registry":
        registry.write_text('{"rule":"source-B"}', encoding="utf-8")
    elif changed == "baseline":
        baseline.write_bytes(b"another-baseline-source")
    elif changed == "policy":
        args["resolved_policy"]["door_gap_w"] = 2.0
    elif changed == "locked_width":
        args["locked_inputs"]["items"][0]["cabinet_outer_width_mm"] = 450.0
    elif changed == "engine":
        args["engine_sha256"] = "c" * 64
    elif changed == "commit":
        args["engine_commit"] = "d" * 40
    elif changed == "build":
        args["build_id"] = "another-attested-build"
    else:
        args["coordinate_contract_revision"] = "2"
        with pytest.raises(PrepareEvidenceError, match="unsupported frame contract"):
            build_resource_evidence(**args)
        return
    current = build_resource_evidence(**args)
    with pytest.raises(PrepareEvidenceError) as exc:
        assert_snapshot_current(first, current)
    assert exc.value.code == "WHD_PREPARE_STALE"


@pytest.mark.parametrize("missing", ["registry", "baseline", "policy", "inputs"])
def test_missing_source_must_fail_closed(tmp_path, missing):
    root, registry, baseline = _source(tmp_path)
    args = _arguments(root)
    if missing == "registry":
        registry.unlink()
    elif missing == "baseline":
        baseline.unlink()
    elif missing == "policy":
        args["resolved_policy"] = {}
    else:
        args["locked_inputs"] = {}
    with pytest.raises(PrepareEvidenceError):
        build_resource_evidence(**args)


@pytest.mark.parametrize("candidate", ["../outside.dxf", "/tmp/abs.dxf", "a/./b.dxf", "C:/outside.dxf", "a\\b.dxf"])
def test_untrusted_baseline_paths_fail_closed(tmp_path, candidate):
    root, _, _ = _source(tmp_path)
    args = _arguments(root)
    args["baseline_paths"] = [candidate]
    with pytest.raises(PrepareEvidenceError) as exc:
        build_resource_evidence(**args)
    assert exc.value.code in {"WHD_RESOURCE_PATH_INVALID", "WHD_RESOURCE_UNVERIFIED"}


def test_duplicate_or_symlinked_baselines_fail_closed(tmp_path):
    root, _, baseline = _source(tmp_path)
    args = _arguments(root)
    args["baseline_paths"] *= 2
    with pytest.raises(PrepareEvidenceError):
        build_resource_evidence(**args)
    args["baseline_paths"] = ["基準檔/金庫型/門.dxf"]
    replacement = baseline.with_name("原始備份.dxf")
    baseline.rename(replacement)
    try:
        baseline.symlink_to(replacement)
    except (OSError, NotImplementedError):
        pytest.skip("filesystem denies symlink creation")
    with pytest.raises(PrepareEvidenceError):
        build_resource_evidence(**args)


def test_tampered_receipt_and_nan_policy_fail_closed(tmp_path):
    root, _, _ = _source(tmp_path)
    args = _arguments(root)
    original = build_resource_evidence(**args)
    forged = {
        "snapshot": dict(original["snapshot"]),
        "environment_fingerprint": original["environment_fingerprint"],
    }
    forged["snapshot"]["build_id"] = "tampered"
    with pytest.raises(PrepareEvidenceError) as exc:
        assert_snapshot_current(original, forged)
    assert exc.value.code == "WHD_PREPARE_STALE"
    args["resolved_policy"]["door_gap_w"] = float("nan")
    with pytest.raises(PrepareEvidenceError) as exc:
        build_resource_evidence(**args)
    assert exc.value.code == "WHD_PREPARE_INPUT_INVALID"


def test_authoritative_door_size_uses_wHD_manufacturing_api_not_new_formula():
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext, ManufacturingPolicy
    from ae_engine.manufacturing_api import door_finished_face_size

    policy = ManufacturingPolicy(
        default_thickness=2.0, frame_width=25.0,
        door_gap_w=1.0, door_gap_h=1.0,
        door_fold_left=19.0, door_fold_right=19.0,
        door_fold_top=19.0, door_fold_bottom=19.0,
        indicator_box_fold=49.0,
    )
    context = ManufacturingContext(policy=policy)
    spec = DoorPartSpec(
        width=500.0, height=600.0, thickness=2.0,
        frame_width=25.0, model_name="金庫型",
    )
    expected_w, expected_h = door_finished_face_size(spec, context)
    resolved = resolve_authoritative_door_inputs(spec, context)
    assert resolved["finished_face_dimensions_mm"] == {
        "width": expected_w, "height": expected_h,
    }
    assert resolved["resolved_policy"]["door_gap_w"] == 1.0
    assert resolved["target_frame_certified"] is False
    assert "origin_xyz_mm" not in resolved
    assert "prepare_token" not in resolved
    with pytest.raises(PrepareEvidenceError):
        resolve_authoritative_door_inputs({"width": 500}, context)
