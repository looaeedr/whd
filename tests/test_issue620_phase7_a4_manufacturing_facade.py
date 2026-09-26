import importlib
import inspect


def test_p7_r_d_saved_dxf_verification_has_bounded_owner():
    from ae_engine import manufacturing_api

    owner = importlib.import_module('ae_engine.manufacturing_verification')
    facade_source = inspect.getsource(
        manufacturing_api.verify_saved_resolved_manufacturing_geometry_dxf
    )
    assert '_manufacturing_verification.verify_saved_resolved_manufacturing_geometry_dxf' in facade_source
    assert 'ResolvedDxfAcceptanceIssue' not in facade_source
    assert 'root.glob' not in facade_source

    owner_source = inspect.getsource(owner)
    assert 'def verify_saved_part_render_data_dxf' in owner_source
    assert 'def verify_saved_resolved_manufacturing_geometry_dxf' in owner_source
    for forbidden in (
        'from .manufacturing_api import',
        'import manufacturing_api',
        'gui',
        'fold_designer_bridge',
    ):
        assert forbidden not in owner_source


def test_p7_r_d_dxf_export_sink_has_bounded_owner():
    from ae_engine import manufacturing_api

    owner = importlib.import_module('ae_engine.manufacturing_export')
    save_source = inspect.getsource(manufacturing_api.save_part_render_data_dxf)
    resolved_source = inspect.getsource(
        manufacturing_api.save_resolved_manufacturing_geometry_dxf
    )
    assert '_manufacturing_export.save_part_render_data_dxf' in save_source
    assert 'tempfile.mkstemp' not in save_source
    assert '_manufacturing_export.save_resolved_manufacturing_geometry_dxf' in resolved_source
    assert '_resolved_physical_render_parts' not in resolved_source

    owner_source = inspect.getsource(owner)
    assert 'def save_part_render_data_dxf' in owner_source
    assert 'def resolved_physical_render_parts' in owner_source
    assert 'def save_resolved_manufacturing_geometry_dxf' in owner_source
    for forbidden in (
        'from .manufacturing_api import',
        'import manufacturing_api',
        'gui',
        'fold_designer_bridge',
    ):
        assert forbidden not in owner_source
