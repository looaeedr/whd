"""#2517: Engine owns physical dimension evidence, GUI only formats text."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import inspect

import pytest
from shapely.geometry import box

from ae_engine import manufacturing_api
from ae_engine.assembly_physical_dimensions import AssemblyPhysicalDimensionEvidence
from ae_engine.contracts import FoldProfileSegment
from phase6_final_scene_projection import _phase6_assembly_physical_dimension_lines


def _piece(role, segments):
    return SimpleNamespace(role=role, fold_profile=tuple(segments))


def _part(key, *, pieces=(), material=None, metadata=None):
    return SimpleNamespace(
        part_key=key,
        render_data=SimpleNamespace(
            pieces=tuple(pieces), material=material, metadata=metadata or {},
        ),
    )


def test_engine_adjacent_bend_and_explicit_formed_length_do_not_mutate_source():
    segments = (
        FoldProfileSegment(length=22.0, angle=-90.0),
        FoldProfileSegment(length=100.0, angle=-90.0),
        FoldProfileSegment(length=18.0, formed_length=19.0),
    )
    part = _part("box_body", pieces=(_piece("left_side", segments),))
    before = deepcopy(part)
    evidence = manufacturing_api.project_assembly_physical_dimension_evidence(
        part, thickness=2.0,
    )
    assert evidence == (AssemblyPhysicalDimensionEvidence(
        role="left_side", fold_outside=(24.0, 104.0, 19.0),
    ),)
    assert part == before
    with pytest.raises(FrozenInstanceError):
        evidence[0].role = "right_side"
    assert _phase6_assembly_physical_dimension_lines(part, thickness=2.0) == (
        "左側板：折後各段包外 24 / 104 / 19 mm（依展開順序）",
    )


def test_real_receiving_side_back_fold_evidence_matches_physical_side_roles():
    from tests.test_piece_level_joint_geometry import _receiving_body_part

    body = _receiving_body_part()
    evidence = manufacturing_api.project_assembly_physical_dimension_evidence(
        body, thickness=2.0,
    )
    assert tuple(item.role for item in evidence) == ("left_side", "right_side")
    physical = {piece.role: piece for piece in body.render_data.pieces}
    for item in evidence:
        assert len(item.fold_outside) == len(physical[item.role].fold_profile)
        assert all(value > 0 for value in item.fold_outside)
    assert len(_phase6_assembly_physical_dimension_lines(body, thickness=2.0)) == 2


def test_divider_physical_contract_and_nonphysical_parts_are_read_only():
    mat = box(5, 7, 105, 87)
    part = _part(
        "box_body:divider:1", material=mat,
        metadata={"physical_geometry_contract": {
            "fw_physical_face": {"outside_dimension": 22},
            "core_physical_segment": {"outside_dimension": 40},
        }},
    )
    witness = mat.wkb
    assert manufacturing_api.project_assembly_physical_dimension_evidence(
        part, thickness=2.0,
    ) == (AssemblyPhysicalDimensionEvidence(
        role="divider", material_extent=(100.0, 80.0),
        fw_outside=22, core_outside=40,
    ),)
    assert _phase6_assembly_physical_dimension_lines(part, thickness=2.0) == (
        "中隔：展開外框 100 × 80 mm；FW包外 22、核心包外 40",
    )
    assert mat.wkb == witness
    assert manufacturing_api.project_assembly_physical_dimension_evidence(
        _part("door", material=mat), thickness=2.0,
    ) == ()
    assert manufacturing_api.project_assembly_physical_dimension_evidence(
        _part("box_body:divider:2"), thickness=2.0,
    ) == ()


def test_gui_only_formats_engine_evidence(monkeypatch):
    part = object()
    calls = []

    def engine(request, *, thickness):
        calls.append((request, thickness))
        return (AssemblyPhysicalDimensionEvidence(
            role="right_side", fold_outside=(22.5, 105.0),
        ),)

    monkeypatch.setattr(
        manufacturing_api, "project_assembly_physical_dimension_evidence", engine,
    )
    assert _phase6_assembly_physical_dimension_lines(part, thickness=1.5) == (
        "右側板：折後各段包外 22.5 / 105 mm（依展開順序）",
    )
    assert calls == [(part, 1.5)]
    source = inspect.getsource(_phase6_assembly_physical_dimension_lines)
    assert "manufacturing_api.project_assembly_physical_dimension_evidence" in source
    assert "apply_outside_dimension_compensation" not in source
    assert "material.bounds" not in source
