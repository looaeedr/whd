import importlib


def test_issue351_compatibility_gate():
    gate = importlib.import_module("tools.issue351_t6_compatibility_gate")
    assert gate.main() == 0


def test_issue351_runtime_shared_reexports_remain_identical_after_t4():
    import fold_designer_bridge as bridge
    import phase6_manufacturing_geometry as owner
    from tools.issue351_t6_compatibility_gate import OWNER_ONLY, SHARED_REEXPORTS

    for name in SHARED_REEXPORTS:
        assert getattr(bridge, name) is getattr(owner, name)

    for name in OWNER_ONLY:
        assert hasattr(owner, name)
        assert not hasattr(bridge, name)
