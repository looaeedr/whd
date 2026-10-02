import importlib
import inspect


def test_p7_r_e_generic_planar_collision_has_single_bounded_owner():
    from ae_engine import assembly_collision

    owner = importlib.import_module('ae_engine.collision_backprojection')

    detect_source = inspect.getsource(assembly_collision.detect_planar_collision)
    project_source = inspect.getsource(
        assembly_collision.project_collision_to_endcap_relief
    )
    assert '_collision_backprojection.detect_planar_collision' in detect_source
    assert '.intersection(' not in detect_source
    assert '_collision_backprojection.project_collision_to_endcap_relief' in project_source
    assert '.buffer(' not in project_source

    owner_source = inspect.getsource(owner)
    assert 'def detect_planar_collision' in owner_source
    assert 'def project_collision_to_endcap_relief' in owner_source
    assert owner_source.count('.intersection(') == 1
    assert owner_source.count('.buffer(') == 1
    for forbidden in (
        'from .assembly_collision import',
        'from .manufacturing_api import',
        'import manufacturing_api',
    ):
        assert forbidden not in owner_source


def test_p7_r_e_divider_relief_has_bounded_owner():
    from ae_engine import assembly_collision

    owner = importlib.import_module('ae_engine.divider_relief_solver')
    assert assembly_collision.DividerFrontFoldReliefCandidate is owner.DividerFrontFoldReliefCandidate

    build_source = inspect.getsource(assembly_collision.build_divider_front_fold_relief_candidate)
    verify_source = inspect.getsource(assembly_collision.verify_divider_front_fold_relief)
    front_source = inspect.getsource(assembly_collision._divider_front_fold_segments)
    assert '_divider_relief_solver.build_divider_front_fold_relief_candidate' in build_source
    assert '_divider_relief_solver.verify_divider_front_fold_relief' in verify_source
    assert '_divider_relief_solver.divider_front_fold_segments' in front_source
    assert 'shapely' not in build_source
    assert 'physical_footprint_2d' not in verify_source

    owner_source = inspect.getsource(owner)
    assert 'class DividerFrontFoldReliefCandidate' in owner_source
    assert 'def build_divider_front_fold_relief_candidate' in owner_source
    assert 'def verify_divider_front_fold_relief' in owner_source
    for forbidden in (
        'from .assembly_collision import',
        'from .manufacturing_api import',
        'import manufacturing_api',
    ):
        assert forbidden not in owner_source


def test_p7_r_e_endcap_world_relief_has_bounded_owner():
    from ae_engine import assembly_collision

    owner = importlib.import_module('ae_engine.endcap_world_relief_solver')
    facade_source = inspect.getsource(
        assembly_collision.solve_world_backprojected_endcap_relief
    )
    assert '_endcap_world_relief_solver.solve_world_backprojected_endcap_relief' in facade_source
    assert 'lookup_certified_endcap_relief' not in facade_source
    assert 'folded_mesh_with_flat_uv_from_polygon' not in facade_source

    owner_source = inspect.getsource(owner)
    assert 'def solve_world_backprojected_endcap_relief' in owner_source
    assert 'lookup_certified_endcap_relief' in owner_source
    assert 'folded_mesh_with_flat_uv_from_polygon' in owner_source
    for forbidden in (
        'from .assembly_collision import',
        'from .manufacturing_api import',
        'import manufacturing_api',
    ):
        assert forbidden not in owner_source
