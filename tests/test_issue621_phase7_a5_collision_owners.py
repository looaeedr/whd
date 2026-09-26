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
