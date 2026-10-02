import inspect


def test_p7_r_c_baseline_resources_has_bounded_owner():
    from ae_engine import ae
    from ae_engine import baseline_resources

    assert "基準檔" not in inspect.getsource(ae.baseline_root_path)
    assert "_baseline_resources.baseline_root_path" in inspect.getsource(ae.baseline_root_path)
    assert ae.baseline_expected_path("", "門.dxf") is None

    source = inspect.getsource(baseline_resources)
    assert "def baseline_root_path" in source
    assert "def indicator_shared_baseline_model_name" in source
    for forbidden in (
        "sheetmetal_geometry",
        "sheetmetal_features",
        "dxf_serialization",
        "manufacturing_api",
        "assembly_collision",
        "from . import ae",
    ):
        assert forbidden not in source
