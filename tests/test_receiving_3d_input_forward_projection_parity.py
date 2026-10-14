# -*- coding: utf-8 -*-
"""Hard gate: Fold 3D input is the source; assembly is its forward projection."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine.cabinet_types import receiving
from ae_engine.box_body_structure import project_side_back_3d_input_fold_to_physical
from fold_designer_bridge import (
    _phase6_box_body_piece_part_profiles,
    _phase6_mesh_profiles_for_part,
)
from phase6_final_scene_projection import (
    _phase6_contract_profile_rows,
    _phase6_folded_mesh_from_polygon,
)
from tests.test_issue39_divider_relief import _body_part


@pytest.mark.parametrize('role', ['left_side', 'back', 'right_side'])
def test_single_piece_folded_triangles_are_same_as_input_projected_to_assembly(role):
    snapshot = receiving.apply_family_defaults({'t': 2.0})
    result = _body_part(snapshot).render_data
    piece = next(item for item in result.pieces if item.role == role)
    operator = _phase6_box_body_piece_part_profiles(result, snapshot)['box_body:' + role]
    editor = SimpleNamespace(
        designer_workspace=SimpleNamespace(active_part='box_body:' + role),
        state=SimpleNamespace(profiles=operator),
        _phase6_input_snapshot=snapshot, _settings_values={},
    )
    actual_x, actual_y = _phase6_mesh_profiles_for_part(
        editor, 'box_body:' + role, piece.render_data.material)
    assembly_x = _phase6_contract_profile_rows(piece.fold_profile)
    assert [
        (row.get('phase6_key'), row['len'], row.get('angle'))
        for row in actual_x
    ] == [
        (row.get('phase6_key'), row['len'], row.get('angle'))
        for row in assembly_x
    ]
    y = [{'len':float(piece.render_data.material.bounds[3]
                      - piece.render_data.material.bounds[1])}]
    guides = tuple(piece.render_data.fold_guides or ())
    part_mesh = _phase6_folded_mesh_from_polygon(
        piece.render_data.material, actual_x, actual_y, fold_guides=guides)
    manufacturing_mesh = _phase6_folded_mesh_from_polygon(
        piece.render_data.material, assembly_x, y, fold_guides=guides)
    assert part_mesh == manufacturing_mesh
    assert part_mesh


def test_left_input_controls_physical_bend_locations_not_assembled_world_mesh():
    snap = receiving.apply_family_defaults({'t': 2.0})
    result = _body_part(snap).render_data
    operator = _phase6_box_body_piece_part_profiles(result, snap)['box_body:left_side']
    input_rows = deepcopy(operator['X'])
    physical = project_side_back_3d_input_fold_to_physical(
        input_rows, role='left_side', receiving=True, thickness=2.0)
    assert [sum(row['len'] for row in physical[:i]) for i in range(1, 5)] == [
        22.0, 362.0, 387.0, 413.0]
    input_rows[3]['len'] += 1.0
    altered = project_side_back_3d_input_fold_to_physical(
        input_rows, role='left_side', receiving=True, thickness=2.0)
    assert altered != physical
    assert sum(row['len'] for row in altered) == sum(row['len'] for row in input_rows)
    assert [row['phase6_key'] for row in input_rows] == [
        'zl1', 'zl2', 'fw_left', 'd_left', 'side_rear_bend_left'
    ]
