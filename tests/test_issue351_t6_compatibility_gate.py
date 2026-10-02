import importlib


def test_issue351_compatibility_gate():
    gate = importlib.import_module("tools.issue351_t6_compatibility_gate")
    assert gate.main() == 0


def test_issue351_runtime_shared_reexports_and_pure_service():
    import fold_designer_bridge as bridge
    import phase6_manufacturing_geometry as owner
    import phase6_manufacturing_service as service
    from tools.issue351_t6_compatibility_gate import SHARED_REEXPORTS

    for name in SHARED_REEXPORTS:
        assert getattr(bridge, name) is getattr(owner, name)

    assert callable(service.resolve)
    assert not hasattr(owner, "_phase6_resolve_manufacturing_result")
