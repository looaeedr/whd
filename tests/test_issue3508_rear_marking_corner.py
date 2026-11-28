from dataclasses import replace
from hashlib import sha256
from math import cos, sin, pi
from pathlib import Path

import pytest

from ae_engine import WirePullBoxSpec, manufacturing_api as api
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, write_project

PART_KEYS = ("box_body", "head", "tail", "lid")


def _digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _file_state(directory):
    return {
        path.name: (_digest(path), path.stat().st_mtime_ns)
        for path in Path(directory).iterdir()
        if path.is_file()
    }


def _proposal(spec, *, rear_opening=None):
    hole = CircleFeature(
        4,
        FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        Vec2(400, 150),
        source_type="MANUAL_TEST",
    )
    mark = replace(
        hole,
        layer="MARKING",
        diameter=2,
        offset=Vec2(420, 170),
    )
    proposal = api.propose_wire_pull_holes(
        spec, manual=(("box_body", (hole, mark)),)
    )
    if rear_opening is not None:
        proposal = api.set_wire_pull_rear_opening(
            proposal, flat_bounds=rear_opening
        )
    return proposal


def _write_project(path, spec, proposal):
    snapshot = api.build_wire_pull_project_snapshot(spec, proposal)
    return write_project(
        path,
        {"schema": PROJECT_SCHEMA, "snapshot": snapshot},
    )


@pytest.mark.parametrize("thickness", [1.5, 3.0])
def test_exact_marking_circle_crosses_opening_corner(thickness):
    spec = WirePullBoxSpec(637, 411, 223, thickness)
    face = next(
        face
        for face in api.resolve_standard_cabinet_topology(spec)
        .part("box_body")
        .mounting_faces
        if face.face_id == "rear"
    )
    left, bottom, right_bound, top_bound = face.flat_bounds
    center_u = (left + right_bound) / 2
    center_v = (bottom + top_bound) / 2
    corner_x, corner_y = center_u + 50, center_v + 40
    theta = pi / 128
    opening_bounds = (center_u - 50, center_v - 40, corner_x, corner_y)

    def proposal_for(radial_offset):
        circle = CircleFeature(
            4,
            FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            Vec2(
                corner_x + radial_offset * cos(theta),
                corner_y + radial_offset * sin(theta),
            ),
            layer="MARKING",
        )
        original = api.propose_wire_pull_holes(
            spec, manual=(("box_body", (circle,)),)
        )
        return api.set_wire_pull_rear_opening(
            original, flat_bounds=opening_bounds
        )

    assert proposal_for(2.0003)
    with pytest.raises(ValueError, match="WIRE_PULL_REAR_OPENING_MATERIAL_CONFLICT"):
        proposal_for(1.9997)


def test_unverified_rear_opening_does_not_overwrite_four_existing_dxfs(tmp_path):
    spec = WirePullBoxSpec(637, 411, 223, 3)
    rear = next(
        face
        for face in api.resolve_standard_cabinet_topology(spec)
        .part("box_body")
        .mounting_faces
        if face.face_id == "rear"
    )
    left, bottom, right, top = rear.flat_bounds
    center_u, center_v = (left + right) / 2, (bottom + top) / 2
    bounds = (center_u - 50, center_v - 40, center_u + 50, center_v + 40)

    standard_project = _write_project(
        tmp_path / "standard.p6fold", spec, _proposal(spec)
    )
    standard_source = api.inspect_wire_pull_saved_export(standard_project)
    assert standard_source.manufacturing_blocker is None
    output = tmp_path / "existing-dxfs"
    result = api.save_wire_pull_saved_project_dxf(
        standard_project,
        output,
        expected_source_sha256=standard_source.source_sha256,
    )
    assert tuple(result) == PART_KEYS
    before = _file_state(output)
    assert tuple(sorted(before)) == tuple(
        sorted(f"{part_key}.dxf" for part_key in PART_KEYS)
    )

    candidate = _write_project(
        tmp_path / "rear-opening.p6fold",
        spec,
        _proposal(spec, rear_opening=bounds),
    )
    candidate_source = api.inspect_wire_pull_saved_export(candidate)
    assert candidate_source.manufacturing_blocker == "WIRE_PULL_REAR_COVER_JOINT_UNVERIFIED"
    with pytest.raises(ValueError, match="WIRE_PULL_REAR_COVER_JOINT_UNVERIFIED"):
        api.save_wire_pull_saved_project_dxf(
            candidate,
            output,
            expected_source_sha256=candidate_source.source_sha256,
            overwrite=True,
        )
    after = _file_state(output)
    assert after == before
    print("FOUR_DXFS_BEFORE", before)
    print("FOUR_DXFS_AFTER", after)
