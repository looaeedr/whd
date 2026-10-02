import inspect


def test_p7_r_c_dxf_serialization_has_bounded_owner():
    from ae_engine import ae
    from ae_engine import dxf_serialization
    from ae_engine import manufacturing_api

    assert ae.setup_dxf_layers is dxf_serialization.setup_dxf_layers
    assert ae._add_drawing_scene_to_dxf is dxf_serialization.add_drawing_scene_to_dxf
    assert ae._save_scene_dxf is dxf_serialization.save_scene_dxf

    manufacturing_source = inspect.getsource(manufacturing_api)
    assert "ae._save_scene_dxf" not in manufacturing_source
    assert "save_scene_dxf" in manufacturing_source


def test_p7_r_c_dxf_serialization_does_not_recompute_geometry():
    from ae_engine import dxf_serialization

    source = inspect.getsource(dxf_serialization)
    assert "from .sheetmetal_drawing import" in source
    for forbidden in (
        "sheetmetal_geometry",
        "sheetmetal_features",
        "sheetmetal_part_adapters",
        "manufacturing_api",
        "assembly_collision",
    ):
        assert forbidden not in source

def test_p7_r_c_baseline_source_cache_has_bounded_owner():
    from ae_engine import ae
    from ae_engine import baseline_source

    assert ae.clear_baseline_dxf_source_cache is baseline_source.clear_baseline_dxf_source_cache
    assert ae.force_reload_baseline_dxf_sources is baseline_source.force_reload_baseline_dxf_sources
    assert ae.baseline_source_fingerprint is baseline_source.baseline_source_fingerprint
    assert ae.load_baseline_dxf_source_with_status is baseline_source.load_baseline_dxf_source_with_status
    assert ae.load_baseline_dxf_source is baseline_source.load_baseline_dxf_source
    assert ae._iter_baseline_entities is baseline_source.iter_baseline_entities
    assert ae._baseline_entity_layer is baseline_source.baseline_entity_layer
    assert ae._baseline_cutting_bounds is baseline_source.baseline_cutting_bounds


def test_p7_r_c_baseline_source_owner_is_independent_from_serializer_and_geometry():
    from ae_engine import baseline_source

    source = inspect.getsource(baseline_source)
    assert "dxf_serialization" not in source
    for forbidden in (
        "sheetmetal_geometry",
        "sheetmetal_features",
        "sheetmetal_part_adapters",
        "manufacturing_api",
        "assembly_collision",
    ):
        assert forbidden not in source