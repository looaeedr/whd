import inspect


def test_p7_r_c_stretched_box_body_has_bounded_adapter_owner():
    from ae_engine import ae
    from ae_engine import baseline_scene_adapters

    facade_source = inspect.getsource(ae.get_stretched_box_body_data)
    assert "_baseline_scene_adapters.get_stretched_box_body_data" in facade_source
    assert "build_strip_outline" not in facade_source

    owner_source = inspect.getsource(baseline_scene_adapters)
    assert "chain_builder(" in owner_source
    assert "build_strip_outline" in owner_source
    assert "build_strip_bend_segments" in owner_source
    for forbidden in (
        "from . import ae",
        "manufacturing_api",
        "dxf_serialization",
        "assembly_collision",
    ):
        assert forbidden not in owner_source


def test_p7_r_c_stretched_end_cap_has_bounded_adapter_owner():
    from ae_engine import ae
    from ae_engine import baseline_scene_adapters

    facade_source = inspect.getsource(ae.get_stretched_end_cap_data)
    assert "_baseline_scene_adapters.get_stretched_end_cap_data" in facade_source
    assert "build_endcap_bend_segments" not in facade_source
    assert "build_unknown_endcap_result" not in facade_source

    owner_source = inspect.getsource(baseline_scene_adapters)
    assert "def get_stretched_end_cap_data" in owner_source
    assert "build_endcap_bend_segments" in owner_source
    assert "build_unknown_endcap_result" in owner_source


def test_p7_r_c_stretched_door_has_bounded_adapter_owner():
    from ae_engine import ae
    from ae_engine import baseline_scene_adapters

    facade_source = inspect.getsource(ae.get_stretched_door_data)
    assert "_baseline_scene_adapters.get_stretched_door_data" in facade_source
    assert "msp.query" not in facade_source
    assert "for ent in" not in facade_source

    owner_source = inspect.getsource(baseline_scene_adapters)
    assert "def get_stretched_door_data" in owner_source
    assert "indicator_small_door_window_geometry" in owner_source
    assert "resolve_door_indicator_layout" in owner_source
