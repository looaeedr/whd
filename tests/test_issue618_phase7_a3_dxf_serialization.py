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