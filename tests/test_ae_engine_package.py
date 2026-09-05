from pathlib import Path
import importlib
import inspect
import sys


def test_ae_engine_package_imports_authoritative_modules():
    import ae_engine
    from ae_engine import manufacturing_api
    from ae_engine.contracts import DoorPartSpec
    from ae_engine.sheetmetal_geometry import Vec2
    from ae_engine.sheetmetal_features import CircleFeature

    assert manufacturing_api.DoorPartSpec is DoorPartSpec
    assert manufacturing_api.Vec2 is Vec2
    assert manufacturing_api.CircleFeature is CircleFeature
    assert hasattr(ae_engine, "generate_part")


def test_ae_engine_uses_project_root_for_default_resources():
    from ae_engine import ae

    project_root = Path(__file__).resolve().parents[1]
    assert Path(ae.get_resource_path("config.ini")).resolve() == (project_root / "config.ini").resolve()
    assert Path(ae.get_resource_path("基準檔")).resolve() == (project_root / "基準檔").resolve()


def test_gui_production_imports_ae_engine_not_legacy_core_modules():
    source = Path("gui.py").read_text(encoding="utf-8")
    header = source[: source.index("class BoxCalculatorGUI")]
    assert "import ae_engine.ae as ae" in header
    assert "from ae_engine import manufacturing_api" in header
    assert "from ae_engine.contracts import" in header
    assert "from ae_engine.sheetmetal_geometry import" in header
    assert "from ae_engine.sheetmetal_features import" in header
    assert "from ae_engine.sheetmetal_part_adapters import" in header
    assert "from ae_engine.hole_catalog import" in header
    assert "from ae_engine.sheetmetal_drawing import" in header


def test_legacy_root_core_modules_are_removed():
    names = [
        "ae.py", "contracts.py", "manufacturing_api.py", "sheetmetal_geometry.py",
        "sheetmetal_features.py", "sheetmetal_part_adapters.py", "sheetmetal_drawing.py",
        "hole_catalog.py",
    ]
    root = Path(__file__).resolve().parents[1]
    assert all(not (root / name).exists() for name in names)


def test_strict_feature_surface_predicate_is_core_and_rejects_boundary_touch():
    from ae_engine.sheetmetal_features import (
        CircleFeature,
        FeatureAnchor,
        feature_is_strictly_within_surface,
        feature_surface_from_rect,
    )
    from ae_engine.sheetmetal_geometry import Vec2

    surface = feature_surface_from_rect('face', Vec2(0, 0), Vec2(100, 100))
    inside = CircleFeature(20, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(50, 50))
    touching = CircleFeature(20, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(10, 50))

    assert feature_is_strictly_within_surface(surface, inside, 100, 100) is True
    assert feature_is_strictly_within_surface(surface, touching, 100, 100) is False
