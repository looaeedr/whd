import importlib


def test_issue351_compatibility_gate():
    gate = importlib.import_module("tools.issue351_t6_compatibility_gate")
    assert gate.main() == 0


def test_issue351_runtime_reexports_are_identical():
    import fold_designer_bridge as bridge
    import phase6_manufacturing_geometry as owner
    from tools.issue351_t6_compatibility_gate import MOVED

    for name in MOVED:
        assert getattr(bridge, name) is getattr(owner, name)
